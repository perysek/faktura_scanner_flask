"""
Skrypt naprawiający dane klientów: usuwa prefiks 'p.', poprawia kolejność
first_name/last_name oraz kapitalizację pierwszej litery.

Logika (kolejność kroków ma znaczenie):
  1. PREFIKS: jeśli first_name lub last_name zaczyna się od 'p.' (case-insensitive)
     → usuń ten prefiks (np. 'p.Grażyna' → 'Grażyna').
  2. ZAMIANA: jeśli first_name NIE jest polskim imieniem, ale last_name JEST →
     zamień wartości miejscami (działa na danych po kroku 1).
  3. KAPITALIZACJA: jeśli pierwsza litera first_name lub last_name jest mała →
     zamień na wielką (tylko pierwsza litera, reszta bez zmian).

Użycie:
    python scripts/fix_client_name_order.py           # dry-run (podgląd)
    python scripts/fix_client_name_order.py --apply   # wykonaj zmiany
"""
import sys
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import DB_PATH

# ---------------------------------------------------------------------------
# Zestaw polskich imion (+ popularne ukraińskie/rosyjskie spotykane w salonach)
# Wszystkie małymi literami — porównanie jest case-insensitive
# ---------------------------------------------------------------------------
POLISH_FIRST_NAMES = {
    # Żeńskie
    "ada", "agata", "agnieszka", "aldona", "aleksanda", "aleksandra",
    "alicja", "alina", "amelia", "anastazja", "aneta", "angelika",
    "ania", "anita", "anna", "antonina",
    "barbara", "basia", "beata", "bożena",
    "celina", "dagmara", "danuta", "daria", "diana", "dominika", "dorota",
    "edyta", "ela", "elżbieta", "emilia", "ewa", "ewelina",
    "gabriela", "gosia", "grażyna",
    "hania", "hanna", "helena",
    "iga", "ilona", "irena", "irmina", "iwona", "iza", "izabela",
    "jadwiga", "joanna", "jola", "jolanta", "judyta", "julia", "julita",
    "justyna",
    "kaja", "kalina", "kamila", "karina", "karolina", "kasia", "katarzyna",
    "katia", "kinga", "klaudia", "krystyna",
    "laura", "lena", "leokadia", "lidia", "liliana", "linda", "liudmila",
    "liudmyla", "liza", "luba", "lucyna",
    "magda", "magdalena", "maja", "małgorzata", "magłorzata", "malwina",
    "mandaryna", "marcela", "maria", "marianka", "marianna", "mariola",
    "marlena", "marta", "martyna", "marzena", "michalina", "milena",
    "monika",
    "natalia", "nicol", "nikola",
    "oksana", "ola", "olga", "oliwia",
    "patrycja", "paula", "paulina",
    "radosława", "renata", "róża",
    "sandra", "sara", "sylwia",
    "tamara", "tarama", "teresa",
    "ula", "urszula",
    "viktoria", "viki", "vivienne", "wanda", "weronika", "wiktoria",
    "wioletta",
    "zofia", "zuzanna",
    # Męskie
    "adam", "adrian", "andrii", "andrzej", "artur",
    "bartosz", "bogdan",
    "dariusz", "dawid", "dominik",
    "grzegorz",
    "irek",
    "jacek", "jakub", "jan", "jarek", "jarosław",
    "kamil", "konrad", "krzysztof", "krzysztoł",
    "leszek", "łukasz",
    "maciej", "maciek", "marcin", "marek", "mariusz", "mateusz",
    "michal", "michał", "mikołaj", "mirosław",
    "norbert",
    "patryk", "piotr", "przemek", "przemysław",
    "radosław", "rafal", "rafał", "robert",
    "sebastian", "sławomir", "stanisław", "szymon",
    "tomasz",
    "waldemar", "wiktor", "witold", "wojciech",
}


def normalize(name: str) -> str:
    """Normalizuj imię do małych liter bez wiodących/końcowych spacji."""
    return name.strip().lower()


def is_first_name(name: str) -> bool:
    """Sprawdź, czy podana wartość jest polskim imieniem."""
    return normalize(name) in POLISH_FIRST_NAMES


def strip_p_prefix(name: str) -> str:
    """Usuń prefiks 'p.' (pani/pan) z początku wartości, case-insensitive."""
    stripped = name.strip()
    if stripped.lower().startswith("p."):
        return stripped[2:].strip()
    return stripped


def capitalize_first(name: str) -> str:
    """Zamień pierwszą literę na wielką, resztę pozostaw bez zmian."""
    if not name:
        return name
    return name[0].upper() + name[1:] if name[0].islower() else name


def find_changes(conn: sqlite3.Connection) -> list[dict]:
    """
    Znajdź klientów wymagających poprawek w następującej kolejności kroków:
      1. PREFIKS: usuń 'p.' z początku first_name / last_name
      2. ZAMIANA: jeśli first_name nie jest imieniem, a last_name jest → zamień
      3. KAPITALIZACJA: jeśli pierwsza litera jest mała → popraw

    Zwraca tylko rekordy, gdzie coś się zmienia.
    """
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, first_name, last_name FROM clients")
    rows = cursor.fetchall()

    changes = []
    for row in rows:
        old_fn = row["first_name"] or ""
        old_ln = row["last_name"] or ""

        fn = old_fn
        ln = old_ln

        # Krok 1: usuń prefiks 'p.' jeśli istnieje
        prefix_removed = False
        fn_stripped = strip_p_prefix(fn)
        ln_stripped = strip_p_prefix(ln)
        if fn_stripped != fn or ln_stripped != ln:
            prefix_removed = True
        fn = fn_stripped
        ln = ln_stripped

        # Krok 2: zamiana kolejności jeśli wymagana (na danych po usunięciu prefiksu)
        swapped = False
        if ln and not is_first_name(fn) and is_first_name(ln):
            fn, ln = ln, fn
            swapped = True

        # Krok 3: kapitalizacja pierwszej litery (po ewentualnej zamianie)
        new_fn = capitalize_first(fn)
        new_ln = capitalize_first(ln)

        # Zapisz tylko jeśli coś się zmieni względem oryginalnych wartości
        if new_fn != old_fn or new_ln != old_ln:
            ops = []
            if prefix_removed:
                ops.append("PREFIKS")
            if swapped:
                ops.append("ZAMIANA")
            if new_fn != fn or new_ln != ln:
                ops.append("KAPITALIZACJA")
            changes.append({
                "id": row["id"],
                "old_first": old_fn,
                "old_last": old_ln,
                "new_first": new_fn,
                "new_last": new_ln,
                "ops": "+".join(ops) if ops else "KAPITALIZACJA",
            })

    return changes


def apply_changes(conn: sqlite3.Connection, changes: list[dict]) -> int:
    """Zastosuj wszystkie obliczone zmiany w bazie danych."""
    cursor = conn.cursor()
    for c in changes:
        cursor.execute(
            "UPDATE clients SET first_name = ?, last_name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (c["new_first"], c["new_last"], c["id"]),
        )
    conn.commit()
    return len(changes)


def main():
    dry_run = "--apply" not in sys.argv

    conn = sqlite3.connect(DB_PATH)
    changes = find_changes(conn)

    if not changes:
        print("Nie znaleziono klientow wymagajacych zmian.")
        conn.close()
        return

    # Grupuj według rodzaju operacji dla czytelnego raportu
    multi_op = [c for c in changes if "ZAMIANA" in c["ops"] or "PREFIKS" in c["ops"]]
    caps_only = [c for c in changes if c["ops"] == "KAPITALIZACJA"]

    prefixes_count = sum(1 for c in changes if "PREFIKS" in c["ops"])
    swaps_count    = sum(1 for c in changes if "ZAMIANA" in c["ops"])
    caps_count     = len(caps_only)

    label = "[DRY RUN] " if dry_run else ""

    if multi_op:
        print(f"{label}Zmiany strukturalne ({len(multi_op)}):\n")
        print(f"  {'ID':>4}  {'Operacja':30}  {'Stare':35}  {'Nowe':35}")
        print("  " + "-" * 110)
        for c in multi_op:
            old = f"{c['old_first']} / {c['old_last']}"
            new = f"{c['new_first']} / {c['new_last']}"
            print(f"  {c['id']:>4}  {c['ops']:30}  {old:35}  -> {new}")

    if caps_only:
        print(f"\n{label}Tylko kapitalizacja ({len(caps_only)}):\n")
        print(f"  {'ID':>4}  {'Stare first_name':25}  {'Nowe first_name':25}  {'Stare last_name':25}  {'Nowe last_name':25}")
        print("  " + "-" * 110)
        for c in caps_only:
            print(f"  {c['id']:>4}  {c['old_first']:25}  {c['new_first']:25}  {c['old_last']:25}  {c['new_last']:25}")

    print(f"\nRazem zmian: {len(changes)}  (prefiks: {prefixes_count}, zamiany: {swaps_count}, kapitalizacja: {caps_count})")

    if dry_run:
        print(f"\nTo jest podglad. Aby wykonac zmiany, uruchom z flaga --apply:")
        print(f"  python scripts/fix_client_name_order.py --apply")
    else:
        count = apply_changes(conn, changes)
        print(f"\nZastosowano {count} zmian.")

    conn.close()


if __name__ == "__main__":
    main()
