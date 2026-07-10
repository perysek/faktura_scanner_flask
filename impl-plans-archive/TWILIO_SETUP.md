# Twilio SMS Setup Guide

Przewodnik konfiguracji integracji Twilio z MyWay Beauty Salon.

---

## 1. Utwórz konto Twilio

1. Wejdź na [twilio.com](https://www.twilio.com) i zarejestruj konto.
2. Potwierdź e-mail i numer telefonu (wymagane przez Twilio).
3. Możesz zacząć od **darmowego trial** — dostaniesz $15 kredytu na testy.

> **Trial a produkcja:** Konto trial może wysyłać SMS tylko na numery **zweryfikowane w konsoli Twilio** (Verified Caller IDs). Na produkcję musisz uzupełnić dane firmy i doładować konto.

---

## 2. Pobierz dane uwierzytelniające

Po zalogowaniu wejdź na **Console Dashboard** → [console.twilio.com](https://console.twilio.com):

| Dane | Gdzie znaleźć | Przykład |
|------|---------------|---------|
| **Account SID** | Strona główna konsoli | `ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` |
| **Auth Token** | Strona główna konsoli (kliknij oko) | `your_auth_token_here` |

Skopiuj oba — będą potrzebne w aplikacji.

---

## 3. Zdobądź numer nadawcy SMS

### Opcja A — Numer Twilio (zalecane dla Polski)

1. W konsoli Twilio: **Phone Numbers → Manage → Buy a number**
2. Filtruj po kraju: **Poland** → typ: **Mobile** → zaznacz **SMS**
3. Kup numer — kosztuje ok. $1–2/miesiąc
4. Format numeru: `+48XXXXXXXXX`

> **Uwaga:** Twilio nie oferuje polskich numerów lokalnych ze wszystkimi funkcjami. Numery US (+1) działają do wysyłki do Polski — tanio i bez ograniczeń.

### Opcja B — Numer US (tańszy w trial)

W trial Twilio automatycznie przydziela numer US. Działa do Polski — klienci dostaną SMS z numeru `+1XXXXXXXXXX`. Mniej profesjonalne, ale funkcjonalnie identyczne.

### Opcja C — Alfanumeryczny Sender ID

Zamiast numeru możesz wpisać nazwę, np. `MyWay` (do 11 znaków). 

**Ograniczenia:** Polska **wymaga rejestracji** alfanumerycznych senderów (Twilio Sender ID Registration). Bez rejestracji SMS mogą być odrzucane przez operatorów. Nie zalecane bez wcześniejszego sprawdzenia statusu dla PL.

---

## 4. Skonfiguruj aplikację

Wejdź w aplikacji: **Ustawienia → SMS** (`/settings/sms`)

Dostęp mają tylko użytkownicy z rolą `admin` lub `superuser`.

### Wypełnij dane Twilio

| Pole | Wartość |
|------|---------|
| **Account SID** | Skopiowany z konsoli Twilio (`ACxx...`) |
| **Auth Token** | Skopiowany z konsoli Twilio |
| **Numer nadawcy** | Twój numer Twilio w formacie E.164: `+48XXXXXXXXX` lub `+1XXXXXXXXXX` |
| **Włącz wysyłanie SMS** | Zaznacz dopiero po przetestowaniu połączenia |

Kliknij **Zapisz dane Twilio**.

---

## 5. Przetestuj połączenie

Na stronie `/settings/sms` rozwiń sekcję **Test połączenia Twilio**:

1. Wpisz numer testowy w formacie `+48XXXXXXXXX` (swój telefon)
2. Kliknij **Wyślij test**
3. Aplikacja wyśle: `"Test wiadomości SMS z MyWay Beauty Salon."`
4. Jeśli dostaniesz SMS — integracja działa. Zobaczysz Twilio Message SID w odpowiedzi.

> **Trial:** Numer testowy musi być wcześniej dodany w Twilio Console → **Verified Caller IDs**.

---

## 6. Skonfiguruj typy wiadomości

Aplikacja ma 3 wbudowane typy SMS (nieusuwalne). Każdy możesz włączyć/wyłączyć niezależnie:

| Typ | Domyślny czas | Cel |
|-----|--------------|-----|
| **Prośba o potwierdzenie** | 48h przed wizytą | Prosi klienta o potwierdzenie — wysyła link `{confirm_url}` |
| **Pierwsze przypomnienie** | 24h przed wizytą | Przypomnienie dzień wcześniej |
| **Drugie przypomnienie** | 2h przed wizytą | Przypomnienie w dniu wizyty |

### Edycja szablonu wiadomości

Kliknij nazwę typu, żeby rozwinąć edytor. Dostępne zmienne:

| Zmienna | Wartość |
|---------|---------|
| `{salon_name}` | Nazwa salonu z konfiguracji (`APP_NAME` w `.env`) |
| `{client_name}` | Imię klienta |
| `{date}` | Data wizyty (format: `DD.MM.YYYY`) |
| `{time}` | Godzina wizyty (format: `HH:MM`) |
| `{services}` | Lista usług, przecinkami |
| `{hours_before}` | Ile godzin do wizyty |
| `{confirm_url}` | Unikalna URL do potwierdzenia (token UUID) |

**Przykładowy szablon:**
```
Cześć {client_name}! Przypominamy o wizycie w {salon_name} w dniu {date} o {time}.
Usługi: {services}.
Potwierdź wizytę: {confirm_url}
```

> **Licznik znaków:** Edytor liczy znaki na bieżąco. SMS do 160 znaków = 1 wiadomość. Powyżej — dzielony na segmenty (każdy ~153 znaki), co zwiększa koszt.

### Włączenie automatycznej wysyłki

Każdy typ ma checkbox **"Włącz automatyczne wysyłanie"**. Po zaznaczeniu i zapisaniu — scheduler co 15 minut sprawdza wizyty w oknie ±15 minut od docelowego czasu i wysyła SMS automatycznie. Każdy typ jest wysyłany do danej wizyty tylko raz.

---

## 7. Ustaw BASE_URL w .env

Link potwierdzenia `{confirm_url}` generowany jest na podstawie zmiennej `BASE_URL`. Sprawdź `.env` na serwerze:

```bash
# Na serwerze Vultr:
grep BASE_URL /opt/my-way-beauty-salon/.env
```

Jeśli brak — dodaj:

```env
BASE_URL=https://twoja-domena.pl
```

lub dla IP:

```env
BASE_URL=http://70.34.252.120
```

Bez tej zmiennej link będzie wskazywał na `http://localhost:5000` — niedziałający z perspektywy klienta.

---

## 8. Formaty numerów telefonów klientów

Aplikacja automatycznie normalizuje numery do formatu E.164 przed wysyłką:

| Numer w bazie | Po normalizacji |
|---------------|-----------------|
| `501234567` | `+48501234567` |
| `0501234567` | `+48501234567` |
| `48501234567` | `+48501234567` |
| `+48 501 234 567` | `+48501234567` |
| `+48501234567` | `+48501234567` (bez zmian) |

Klienci bez numeru telefonu są automatycznie pomijani przy wysyłce zbiorowej.

---

## 9. Ręczna wysyłka ze szczegółów wizyty

Po aktywacji SMS (krok 4), w widoku szczegółów wizyty (`/appointment/<id>`) pojawia się przycisk **SMS**. Rozwijalne menu pozwala wysłać dowolny typ wiadomości jednym kliknięciem. Każda wysyłka jest logowana w panelu **Historia SMS** na dole strony.

---

## 10. Podgląd historii wysyłek

- **Na poziomie wizyty:** panel „Historia SMS" w szczegółach wizyty
- **Globalny log:** `/settings/sms/log` — wszystkie SMS posortowane chronologicznie, ze statusem, numerem i treścią
- **Statystyki:** `/settings/sms` — widżety MTD (bieżący miesiąc / ostatnie 3 miesiące): wysłane, nieudane, prośby o potwierdzenie, odpowiedzi klientów

---

## 11. Koszty Twilio (orientacyjnie, 2025)

| Operacja | Koszt |
|----------|-------|
| SMS wychodzący do Polski (numer US) | ~$0.04–0.07/SMS |
| SMS wychodzący do Polski (numer PL) | ~$0.05–0.08/SMS |
| Numer Twilio miesięcznie | ~$1–2 |

Dla 300 wizyt/miesiąc z 2 SMS każda ≈ 600 SMS ≈ **~$30–42/miesiąc**.

---

## Troubleshooting

### SMS nie docierają po włączeniu

1. Sprawdź logi: `/settings/sms/log` — czy status to `failed`?
2. Sprawdź logi serwera: `journalctl -u my-way-beauty-salon -n 50`
3. Najczęstsze przyczyny: nieprawidłowy Auth Token, zablokowany numer nadawcy przez operatora, klient bez numeru w bazie

### `21608 — The number is unverified` (konto trial)

Numer odbiorcy nie jest na liście Verified Caller IDs w konsoli Twilio. Dodaj go w: **Console → Phone Numbers → Verified Caller IDs → Add**.

### Link potwierdzenia prowadzi do localhost

Ustaw `BASE_URL` w `.env` na serwerze (patrz krok 7) i zrestartuj usługę:
```bash
systemctl restart my-way-beauty-salon
```

### Scheduler nie wysyła automatycznie

Sprawdź czy `is_active = true` w `sms_settings` i czy dany typ ma `is_enabled = true`. Scheduler działa tylko gdy oba warunki są spełnione.
