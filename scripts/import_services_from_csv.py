"""
Skrypt importu usług z pliku CSV do tabeli 'services' w bazie danych.

Plik CSV powinien mieć nagłówek: name;price;duration_minutes
Brakujące pola modelu Service uzupełniane są wartościami domyślnymi.
Kategoria przypisywana automatycznie na podstawie słów kluczowych w nazwie.

Użycie:
    python scripts/import_services_from_csv.py                         # dry-run
    python scripts/import_services_from_csv.py --apply                 # wykonaj import
    python scripts/import_services_from_csv.py --apply services.csv    # własny plik
"""
import csv
import sys
import sqlite3
import unicodedata
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import DB_PATH

DEFAULT_CSV = PROJECT_ROOT / "services.csv"

# ---------------------------------------------------------------------------
# Mapowanie słów kluczowych → kategoria (pierwsza pasująca wygrywa)
# Wszystkie słowa kluczowe podane bez polskich znaków diakrytycznych —
# porównanie wykonywane po usunięciu akcentów (NFD normalization), więc
# "masaż".lower() → "masaz" i pasuje do klucza "masaz".
#
# Wartości CHECK w bazie: 'Strzyżenie','Koloryzacja','Stylizacja','Trwała',
#   'Pielęgnacja','Masaż','Manicure','Pedicure','Makijaż','Inne'
# ---------------------------------------------------------------------------
CATEGORY_RULES: list[tuple[list[str], str]] = [
    (["masaz", "masa ", "lomi", "kobido", "antycellul", "sportow", "tkanek"],  "Masaż"),
    (["pedicure", "pedi ", "stop", "podniesienie paznokci", "frezowanie"],     "Pedicure"),
    (["manicure", "mani ", "hybrydy", "hybryda", "ibx", "naprawa paznokcia",
      "zdj. hyb"],                                                              "Manicure"),
    (["przedluzenie", "uzupelnienie", "uzupe", "stylizacji", "zelowej",
      "zel/akryl", "zel/ akryl"],                                             "Stylizacja"),
    (["makijaz"],                                                               "Makijaż"),
    (["regulacja brwi", "henna", "depilacja"],                                 "Pielęgnacja"),
    (["strzyzenie", "koloryzacja", "trwala"],                                  "Strzyżenie"),
]


def strip_diacritics(s: str) -> str:
    """Usuń polskie znaki diakrytyczne (ą→a, ę→e, ż→z, …) dla porównania."""
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


def assign_category(name: str) -> str:
    """Przypisz kategorię na podstawie słów kluczowych w nazwie usługi.

    Porównanie jest case-insensitive i ignoruje polskie znaki diakrytyczne.
    """
    normalized = strip_diacritics(name.lower())
    for keywords, category in CATEGORY_RULES:
        if any(kw in normalized for kw in keywords):
            return category
    return "Inne"


def fix_mojibake(s: str) -> str:
    """Napraw podwójne kodowanie (CP1250 bajtów UTF-8 zapisanych jako UTF-8).

    Plik CSV miał polskie znaki zakodowane w UTF-8, ale bajty UTF-8 zostały
    błędnie potraktowane jako znaki CP1250 i ponownie zapisane jako UTF-8.
    Odwrotność: encode('cp1250') → decode('utf-8').
    """
    try:
        return s.encode("cp1250").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def load_csv(path: Path) -> list[dict]:
    """Wczytaj plik CSV i zwróć listę wierszy jako słowniki."""
    rows = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            name = fix_mojibake(row.get("name", "").strip())
            if not name:
                continue
            try:
                price = float(row.get("price", "0").strip())
            except ValueError:
                price = 0.0
            try:
                duration = int(row.get("duration_minutes", "0").strip())
            except ValueError:
                duration = 0
            rows.append({"name": name, "price": price, "duration_minutes": duration})
    return rows


def find_changes(conn: sqlite3.Connection, rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Podziel wiersze na nowe (do wstawienia) i już istniejące (pominięte).

    Duplikat = ten sam name + price już istnieje w tabeli.
    """
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT name, price FROM services")
    existing = {(r["name"], float(r["price"])) for r in cursor.fetchall()}

    to_insert = []
    skipped = []
    for row in rows:
        key = (row["name"], row["price"])
        if key in existing:
            skipped.append(row)
        else:
            to_insert.append(row)
    return to_insert, skipped


def apply_insert(conn: sqlite3.Connection, to_insert: list[dict]) -> int:
    """Wstaw nowe rekordy do tabeli services."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor = conn.cursor()
    for row in to_insert:
        cursor.execute(
            """
            INSERT INTO services
                (name, category, duration_minutes, price, currency,
                 service_type, description, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'PLN', 'main', NULL, 1, ?, ?)
            """,
            (
                row["name"],
                assign_category(row["name"]),
                row["duration_minutes"],
                row["price"],
                now,
                now,
            ),
        )
    conn.commit()
    return len(to_insert)


def main():
    dry_run = "--apply" not in sys.argv

    # Ścieżka do pliku CSV: ostatni argument nie zaczynający się od '--'
    csv_path = DEFAULT_CSV
    for arg in sys.argv[1:]:
        if not arg.startswith("--"):
            csv_path = Path(arg)
            break

    if not csv_path.exists():
        print(f"[BŁĄD] Nie znaleziono pliku: {csv_path}")
        sys.exit(1)

    print(f"Plik CSV:    {csv_path}")
    print(f"Baza danych: {DB_PATH}")
    print("-" * 60)

    rows = load_csv(csv_path)
    print(f"Wierszy w pliku: {len(rows)}")

    conn = sqlite3.connect(DB_PATH)
    to_insert, skipped = find_changes(conn, rows)

    label = "[DRY RUN] " if dry_run else ""

    print(f"\n{label}Do wstawienia ({len(to_insert)}):\n")
    print(f"  {'Nazwa':<50}  {'Cena':>6}  {'Czas':>5}  {'Kategoria'}")
    print("  " + "-" * 85)
    for row in to_insert:
        cat = assign_category(row["name"])
        print(f"  {row['name']:<50}  {row['price']:>6.2f}  {row['duration_minutes']:>4}m  {cat}")

    if skipped:
        print(f"\n{label}Juz istnieja, pominiete ({len(skipped)}):\n")
        for row in skipped:
            print(f"  - {row['name']} ({row['price']:.2f} zl)")

    if dry_run:
        print(f"\nTo jest podglad. Aby wykonac import, uruchom z flaga --apply:")
        print(f"  python scripts/import_services_from_csv.py --apply")
    else:
        count = apply_insert(conn, to_insert)
        print(f"\nZaimportowano {count} uslug. Pominieto {len(skipped)} duplikatow.")

    conn.close()


if __name__ == "__main__":
    main()
