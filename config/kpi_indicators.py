"""
Definicje 20 miesięcznych wskaźników biznesowych (10 procesów × effectiveness +
efficiency), zgodnie z ramą ISO 9001 / IATF 16949 opisaną w
BUSINESS_PROCESS_KPI_REVIEW.md.

Każdy wskaźnik ma unikalny `key`, który musi mieć odpowiadającą metodę
obliczeniową w `repositories/analytics/kpi_matrix_repository.py`
(`KpiMatrixRepository._COMPUTE[key]`).

`target` / `direction` to wartości domyślne — decyzja biznesowa właściciela
salonu, nie coś wyliczanego z danych. Do ręcznej korekty w tym pliku (brak
UI do edycji celów w tej wersji).
"""

PROCESSES = [
    {
        'id': 'P1',
        'name': 'Rezerwacja i realizacja wizyt',
        'indicators': [
            {'key': 'p1_completion_rate', 'name': 'Wskaźnik realizacji wizyt',
             'kind': 'eff', 'unit': '%', 'direction': '>', 'target': 85},
            {'key': 'p1_occupancy', 'name': 'Obłożenie salonu',
             'kind': 'effic', 'unit': '%', 'direction': '>', 'target': 60},
        ],
    },
    {
        'id': 'P2',
        'name': 'Świadczenie usług i jakość obsługi',
        'indicators': [
            {'key': 'p2_satisfaction', 'name': 'Średnia ocena satysfakcji klientów',
             'kind': 'eff', 'unit': '1-5', 'direction': '>', 'target': 4.5},
            {'key': 'p2_revenue_per_hour', 'name': 'Przychód na godzinę usługi',
             'kind': 'effic', 'unit': 'PLN/h', 'direction': '>', 'target': 150},
        ],
    },
    {
        'id': 'P3',
        'name': 'Zarządzanie relacjami z klientem i retencja',
        'indicators': [
            {'key': 'p3_retention', 'name': 'Wskaźnik retencji klientów (90 dni)',
             'kind': 'eff', 'unit': '%', 'direction': '>', 'target': 60},
            {'key': 'p3_visits_per_client', 'name': 'Średnia liczba wizyt na klienta',
             'kind': 'effic', 'unit': 'wizyt/kl.', 'direction': '>', 'target': 1.2},
        ],
    },
    {
        'id': 'P4',
        'name': 'Zarządzanie cennikiem i ofertą usług',
        'indicators': [
            {'key': 'p4_price_update_coverage', 'name': 'Aktualność cennika',
             'kind': 'eff', 'unit': '%', 'direction': '>', 'target': 5},
            {'key': 'p4_price_realisation', 'name': 'Realizacja ceny katalogowej',
             'kind': 'effic', 'unit': '%', 'direction': '>', 'target': 95},
        ],
    },
    {
        'id': 'P5',
        'name': 'Zarządzanie zasobami ludzkimi',
        'indicators': [
            {'key': 'p5_utilisation', 'name': 'Średnie wykorzystanie zespołu',
             'kind': 'eff', 'unit': '%', 'direction': '>', 'target': 70},
            {'key': 'p5_cost_per_visit', 'name': 'Koszt personelu na wizytę',
             'kind': 'effic', 'unit': 'PLN/wiz.', 'direction': '<', 'target': 80},
        ],
    },
    {
        'id': 'P6',
        'name': 'Komunikacja z klientem — przypomnienia SMS',
        'indicators': [
            {'key': 'p6_noshow_despite_reminder', 'name': 'Niestawiennictwo mimo przypomnienia',
             'kind': 'eff', 'unit': '%', 'direction': '<', 'target': 5},
            {'key': 'p6_sms_delivery_rate', 'name': 'Skuteczność dostawy SMS',
             'kind': 'effic', 'unit': '%', 'direction': '>', 'target': 95},
        ],
    },
    {
        'id': 'P7',
        'name': 'Zarządzanie finansami i rentownością',
        'indicators': [
            {'key': 'p7_net_margin', 'name': 'Marża zysku netto',
             'kind': 'eff', 'unit': '%', 'direction': '>', 'target': 25},
            {'key': 'p7_cost_ratio', 'name': 'Wskaźnik kosztów całkowitych',
             'kind': 'effic', 'unit': '%', 'direction': '<', 'target': 70},
        ],
    },
    {
        'id': 'P8',
        'name': 'Zaopatrzenie i zarządzanie dostawcami',
        'indicators': [
            {'key': 'p8_invoice_settlement', 'name': 'Wskaźnik spłacalności faktur',
             'kind': 'eff', 'unit': '%', 'direction': '>', 'target': 90},
            {'key': 'p8_ocr_confidence', 'name': 'Poziom automatyzacji OCR',
             'kind': 'effic', 'unit': '%', 'direction': '>', 'target': 85},
        ],
    },
    {
        'id': 'P9',
        'name': 'Zarządzanie danymi i dostępem',
        'indicators': [
            {'key': 'p9_import_success', 'name': 'Wskaźnik powodzenia importów',
             'kind': 'eff', 'unit': '%', 'direction': '>', 'target': 90},
            {'key': 'p9_import_duration', 'name': 'Średni czas trwania importu',
             'kind': 'effic', 'unit': 'min', 'direction': '<', 'target': 15},
        ],
    },
    {
        'id': 'P10',
        'name': 'Analiza biznesowa i przegląd zarządzania',
        'indicators': [
            {'key': 'p10_targets_met', 'name': 'Odsetek wskaźników z osiągniętym celem',
             'kind': 'eff', 'unit': '%', 'direction': '>', 'target': 80,
             'unavailable_note': 'Wymaga rejestru corocznego przeglądu zarządzania (§5 BUSINESS_PROCESS_KPI_REVIEW.md) — brak jeszcze takiej tabeli w bazie.'},
            {'key': 'p10_corrective_action_timeliness', 'name': 'Terminowość działań korygujących',
             'kind': 'effic', 'unit': '%', 'direction': '>', 'target': 80,
             'unavailable_note': 'Wymaga rejestru corocznego przeglądu zarządzania (§5 BUSINESS_PROCESS_KPI_REVIEW.md) — brak jeszcze takiej tabeli w bazie.'},
        ],
    },
]
