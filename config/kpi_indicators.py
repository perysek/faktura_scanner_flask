"""
Definicje 16 miesięcznych wskaźników biznesowych (8 procesów × effectiveness +
efficiency), zgodnie z ramą ISO 9001 / IATF 16949 opisaną w
BUSINESS_PROCESS_KPI_REVIEW.md.

Każdy wskaźnik ma unikalny `key`, który musi mieć odpowiadającą metodę
obliczeniową w `repositories/analytics/kpi_matrix_repository.py`
(`KpiMatrixRepository._COMPUTE[key]`).

`target` / `direction` to wartości domyślne — decyzja biznesowa właściciela
salonu, nie coś wyliczanego z danych. Do ręcznej korekty w tym pliku (brak
UI do edycji celów w tej wersji).

`description` zasila hover-tooltip na stronie: co pokazuje wskaźnik, jak jest
liczony, jak go poprawić.
"""

PROCESSES = [
    {
        'id': 'P1',
        'name': 'Rezerwacja i realizacja wizyt',
        'indicators': [
            {'key': 'p1_completion_rate', 'name': 'Wskaźnik realizacji wizyt',
             'kind': 'eff', 'unit': '%', 'direction': '>', 'target': 85,
             'description': 'Co pokazuje: odsetek zaplanowanych wizyt, które faktycznie się odbyły. '
                             'Jak liczony: zrealizowane ÷ (zrealizowane + odwołane + nieobecności) × 100%. '
                             'Jak poprawić: ogranicz odwołania (elastyczniejsze zasady rezerwacji, przypomnienia SMS) '
                             'i nieobecności (potwierdzenia wizyt, listy oczekujących na wolne terminy).'},
            {'key': 'p1_occupancy', 'name': 'Obłożenie salonu',
             'kind': 'effic', 'unit': '%', 'direction': '>', 'target': 35,
             'description': 'Co pokazuje: jaka część realnie dostępnego czasu pracy salonu jest faktycznie wykorzystana. '
                             'Jak liczony: suma godzin zarezerwowanych w zrealizowanych wizytach ÷ suma godzin faktycznie dostępnych × 100%. '
                             'Dostępne godziny liczone per pracownik z jego indywidualnego grafiku (godziny pracy wg dnia tygodnia), '
                             'tylko za okres faktycznego zatrudnienia w danym miesiącu (data zatrudnienia/zwolnienia), '
                             'pomniejszone o zatwierdzone nieobecności. Bieżący miesiąc liczy tylko dni, które już minęły. '
                             'Jak poprawić: aktywna sprzedaż wolnych terminów, promocje w godzinach mniejszego ruchu, lepsze planowanie grafików.'},
        ],
    },
    {
        'id': 'P2',
        'name': 'Świadczenie usług i jakość obsługi',
        'indicators': [
            {'key': 'p2_satisfaction', 'name': 'Średnia ocena satysfakcji klientów',
             'kind': 'eff', 'unit': '1-5', 'direction': '>', 'target': 4.5,
             'description': 'Co pokazuje: średnia z ocen (skala 1–5) wystawianych przez klientów po wizycie. '
                             'Jak liczony: suma ocen ÷ liczba ocenionych wizyt w danym miesiącu. '
                             'Jak poprawić: analizuj niskie oceny per usługa/pracownik, wdrażaj szkolenia, reaguj szybko na negatywny feedback.'},
            {'key': 'p2_revenue_per_hour', 'name': 'Przychód na godzinę usługi',
             'kind': 'effic', 'unit': 'PLN/h', 'direction': '>', 'target': 150,
             'description': 'Co pokazuje: ile przychodu generuje każda godzina faktycznie wykonanej usługi. '
                             'Jak liczony: suma kwot pobranych ÷ (suma czasu trwania usług w minutach ÷ 60). '
                             'Jak poprawić: promuj usługi o wyższej marży, ogranicz rabaty, skracaj przestoje między wizytami.'},
        ],
    },
    {
        'id': 'P3',
        'name': 'Zarządzanie relacjami z klientem i retencja',
        'indicators': [
            {'key': 'p3_retention', 'name': 'Wskaźnik retencji klientów (90 dni)',
             'kind': 'eff', 'unit': '%', 'direction': '>', 'target': 60,
             'description': 'Co pokazuje: jaki odsetek wizyt jest powrotem klienta w ciągu 90 dni od poprzedniej wizyty. '
                             'Jak liczony: wizyty z przerwą ≤90 dni ÷ wszystkie wizyty z poprzednią wizytą w historii × 100%. '
                             'Jak poprawić: programy lojalnościowe, przypomnienia o kolejnej wizycie, konsekwentna jakość obsługi.'},
            {'key': 'p3_visits_per_client', 'name': 'Średnia liczba wizyt na klienta',
             'kind': 'effic', 'unit': 'wizyt/kl.', 'direction': '>', 'target': 1.2,
             'description': 'Co pokazuje: intensywność korzystania z salonu — ile wizyt przypada na jednego unikalnego klienta w miesiącu. '
                             'Jak liczony: zrealizowane wizyty ÷ liczba unikalnych klientów w danym miesiącu. '
                             'Jak poprawić: pakiety/subskrypcje, przypomnienia o cyklicznej pielęgnacji, cross-selling usług uzupełniających.'},
        ],
    },
    {
        'id': 'P4',
        'name': 'Zarządzanie cennikiem i ofertą usług',
        'indicators': [
            {'key': 'p4_price_update_coverage', 'name': 'Aktualność cennika',
             'kind': 'eff', 'unit': '%', 'direction': '>', 'target': 5,
             'description': 'Co pokazuje: regularność przeglądu i aktualizacji cennika — nie jego poziom, tylko czy jest odświeżany. '
                             'Jak liczony: liczba aktywnych usług z zapisaną zmianą ceny w danym miesiącu ÷ liczba aktywnych usług × 100%. '
                             'Jak poprawić: ustal cykliczny (np. kwartalny) przegląd cennika zamiast aktualizacji ad hoc.'},
            {'key': 'p4_price_realisation', 'name': 'Realizacja ceny katalogowej',
             'kind': 'effic', 'unit': '%', 'direction': '>', 'target': 95,
             'description': 'Co pokazuje: relację faktycznie pobranych kwot do cen katalogowych. >100% = dopłaty/upsell, <100% = rabaty. '
                             'Jak liczony: suma kwot pobranych ÷ suma cen katalogowych wykonanych usług × 100%. '
                             'Jak poprawić: ogranicz nieuzasadnione rabaty, szkól zespół w utrzymywaniu dyscypliny cenowej.'},
        ],
    },
    {
        'id': 'P5',
        'name': 'Zarządzanie zasobami ludzkimi',
        'indicators': [
            {'key': 'p5_utilisation', 'name': 'Średnie wykorzystanie zespołu',
             'kind': 'eff', 'unit': '%', 'direction': '>', 'target': 40,
             'description': 'Co pokazuje: średnie wykorzystanie realnego czasu pracy zespołu w danym miesiącu. '
                             'Jak liczony: dla każdego zatrudnionego wtedy pracownika — godziny zarezerwowane ÷ godziny dostępne '
                             '(wg jego grafiku, pomniejszone o zatwierdzone nieobecności) × 100%, uśrednione po pracownikach z jakimikolwiek '
                             'godzinami dostępnymi w tym miesiącu (nieobecni cały miesiąc lub jeszcze niezatrudnieni nie liczą się jako 0%). '
                             'Jak poprawić: wyrównuj obłożenie między pracownikami, planuj urlopy poza szczytem sezonowym.'},
            {'key': 'p5_cost_per_visit', 'name': 'Koszt personelu na wizytę',
             'kind': 'effic', 'unit': 'PLN/wiz.', 'direction': '<', 'target': 80,
             'description': 'Co pokazuje: ile kosztuje pracodawcę (wynagrodzenie + narzuty) jedna zrealizowana wizyta. '
                             'Jak liczony: łączny koszt pracodawcy w miesiącu ÷ liczba zrealizowanych wizyt. '
                             'Jak poprawić: zwiększ liczbę wizyt na pracownika, dostosuj model wynagrodzeń (podstawa vs. prowizja).'},
        ],
    },
    {
        'id': 'P6',
        'name': 'Komunikacja z klientem — przypomnienia SMS',
        'indicators': [
            {'key': 'p6_noshow_despite_reminder', 'name': 'Niestawiennictwo mimo przypomnienia',
             'kind': 'eff', 'unit': '%', 'direction': '<', 'target': 5,
             'description': 'Co pokazuje: skuteczność przypomnień SMS w zapobieganiu nieobecnościom. Niska wartość = przypomnienia działają. '
                             'Jak liczony: wizyty zakończone nieobecnością mimo wysłanego przypomnienia ÷ wszystkie wizyty z wysłanym przypomnieniem × 100%. '
                             'Jak poprawić: zmień treść/czas wysyłki przypomnienia, wprowadź wymagane potwierdzenie wizyty.'},
            {'key': 'p6_sms_delivery_rate', 'name': 'Skuteczność dostawy SMS',
             'kind': 'effic', 'unit': '%', 'direction': '>', 'target': 95,
             'description': 'Co pokazuje: jaki odsetek wysłanych SMS-ów dotarł do odbiorcy (nie odrzucony przez operatora). '
                             'Jak liczony: SMS-y wysłane/dostarczone ÷ (wysłane/dostarczone + nieudane) × 100%. '
                             'Jak poprawić: weryfikuj poprawność numerów telefonów klientów, monitoruj kody błędów dostawy.'},
        ],
    },
    {
        'id': 'P7',
        'name': 'Zarządzanie finansami i rentownością',
        'indicators': [
            {'key': 'p7_net_margin', 'name': 'Marża zysku netto',
             'kind': 'eff', 'unit': '%', 'direction': '>', 'target': 25,
             'description': 'Co pokazuje: jaki procent przychodu zostaje jako zysk netto po odjęciu kosztów personelu i faktur zakupowych. '
                             'Jak liczony: (przychód − koszty personelu − koszty faktur) ÷ przychód × 100%. '
                             'Jak poprawić: zwiększaj przychód (obłożenie, ceny) szybciej niż koszty, kontroluj koszty zakupowe.'},
            {'key': 'p7_cost_ratio', 'name': 'Wskaźnik kosztów całkowitych',
             'kind': 'effic', 'unit': '%', 'direction': '<', 'target': 70,
             'description': 'Co pokazuje: jaki procent przychodu pochłaniają łączne koszty (personel + faktury) — odwrotność marży. '
                             'Jak liczony: (koszty personelu + koszty faktur) ÷ przychód × 100%. '
                             'Jak poprawić: optymalizuj koszty stałe, negocjuj warunki z dostawcami, podnoś efektywność zespołu.'},
        ],
    },
    {
        'id': 'P8',
        'name': 'Zaopatrzenie i zarządzanie dostawcami',
        'indicators': [
            {'key': 'p8_invoice_settlement', 'name': 'Wskaźnik spłacalności faktur',
             'kind': 'eff', 'unit': '%', 'direction': '>', 'target': 90,
             'description': 'Co pokazuje: jaki odsetek faktur zakupowych z danego miesiąca jest opłacony (stan na dziś). '
                             'Jak liczony: faktury o statusie "Opłacona" ÷ wszystkie faktury z danego miesiąca × 100%. '
                             'Uwaga: system nie zapisuje daty faktycznej płatności, więc to migawka na dziś, nie ścisła terminowość. '
                             'Jak poprawić: pilnuj terminów płatności, automatyzuj przypomnienia księgowe.'},
            {'key': 'p8_ocr_confidence', 'name': 'Poziom automatyzacji OCR',
             'kind': 'effic', 'unit': '%', 'direction': '>', 'target': 85,
             'description': 'Co pokazuje: średnią pewność automatycznego odczytu danych z faktur przez OCR. '
                             'Jak liczony: średnia z pola ocr_confidence (0–100%) dla faktur wprowadzonych w danym miesiącu. '
                             'Jak poprawić: popraw jakość skanów/zdjęć faktur, standaryzuj format dokumentów od dostawców.'},
        ],
    },
]

# P9 (Zarządzanie danymi i dostępem — import success/duration) and P10
# (Analiza biznesowa i przegląd zarządzania) were removed 2026-07-17:
# P9 tracked the Caldis migration-period import tooling, not a permanent
# process. P10 needs a dedicated management-review page (with its own
# corrective-action register) before it can show real numbers — planned as
# a separate feature, not folded into this matrix in the meantime.
