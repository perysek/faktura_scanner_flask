"""
Anonymise a raw caldis XLSX export for committing as a test fixture.

Usage:
    python scripts/anonymize_caldis_fixture.py \
        --input  plans/260522-entity-import-step0/2026-05-25T19_43_02-Klienci.xlsx \
        --output tests/fixtures/caldis_entities/clients_sample.xlsx \
        --entity clients

Caldis exports a combined 'Nazwa' field (not separate first/last name columns).
Phone numbers use mixed formats: '509626642' and '501 127 731'.
E-mail is absent from the export (all NULL in production).
"""
import argparse
from pathlib import Path
import pandas as pd

SYNTHETIC_FIRST_NAMES = [
    "Anna", "Maria", "Katarzyna", "Joanna", "Magdalena",
    "Piotr", "Tomasz", "Jakub", "Marcin", "Andrzej",
]


def anonymise_clients(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # caldis exports a single 'Nazwa' column — replace with synthetic combined name
    df['Nazwa'] = [
        f"{SYNTHETIC_FIRST_NAMES[i % len(SYNTHETIC_FIRST_NAMES)]} X."
        for i in range(len(df))
    ]
    if 'Telefon' in df.columns:
        df['Telefon'] = [f"500{str(100000 + i).zfill(6)}" for i in range(len(df))]
    if 'E-mail' in df.columns:
        df['E-mail'] = [f"anon{i}@example.invalid" for i in range(len(df))]
    for col in ('Notatki', 'Pole dodatkowe 1', 'Pole dodatkowe 2', 'Pole dodatkowe 3',
                'Pole dodatkowe 4', 'Pole dodatkowe 5', 'Pole dodatkowe 6'):
        if col in df.columns:
            df[col] = ''
    return df


def anonymise_employees(df: pd.DataFrame) -> pd.DataFrame:
    return anonymise_clients(df)


def anonymise_services(df: pd.DataFrame) -> pd.DataFrame:
    # Services have no PII — keep names and prices as-is for realism
    return df.copy()


ANONYMISERS = {
    'clients':   anonymise_clients,
    'employees': anonymise_employees,
    'services':  anonymise_services,
}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--input',  required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--entity', required=True, choices=list(ANONYMISERS))
    p.add_argument('--limit',  type=int, default=10,
                   help='Max rows in output fixture (default: 10)')
    args = p.parse_args()

    df = pd.read_excel(args.input, dtype=str)
    limit = len(df) if args.entity == 'employees' else args.limit
    df = df.head(limit)
    df = ANONYMISERS[args.entity](df)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(args.output, index=False)
    print(f"Wrote {len(df)} rows to {args.output}")


if __name__ == '__main__':
    main()
