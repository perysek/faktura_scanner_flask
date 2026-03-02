-- Tabela faktur
CREATE TABLE IF NOT EXISTS invoices (
    id SERIAL PRIMARY KEY,
    seller_name TEXT NOT NULL,
    seller_nip TEXT,
    invoice_number TEXT NOT NULL UNIQUE,
    invoice_date DATE NOT NULL,
    bank_account TEXT,
    amount FLOAT NOT NULL,
    currency TEXT DEFAULT 'PLN',
    payment_due_date DATE,
    payment_term TEXT,
    status TEXT DEFAULT 'Nieopłacona',
    pdf_path TEXT,
    ocr_confidence FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_duplicate BOOLEAN DEFAULT FALSE,
    seller_id INTEGER
);

-- Indeksy dla wydajności
CREATE INDEX IF NOT EXISTS idx_invoice_number ON invoices(invoice_number);
CREATE INDEX IF NOT EXISTS idx_invoice_date ON invoices(invoice_date);
CREATE INDEX IF NOT EXISTS idx_seller_name ON invoices(seller_name);

-- Tabela sprzedawców (sellers)
CREATE TABLE IF NOT EXISTS sellers (
    id SERIAL PRIMARY KEY,
    seller_nip TEXT UNIQUE NOT NULL,
    seller_name TEXT NOT NULL,
    address TEXT,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    invoice_count INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_seller_nip ON sellers(seller_nip);
CREATE INDEX IF NOT EXISTS idx_seller_name_search ON sellers(seller_name);

-- Tabela historii zmian (audit log)
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    invoice_id INTEGER,
    action TEXT DEFAULT 'UPDATE',
    field_name TEXT,
    old_value TEXT,
    new_value TEXT,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    entity_type TEXT DEFAULT 'invoice',
    entity_id INTEGER,
    entity_label TEXT,
    user_id INTEGER,
    user_name TEXT
);

-- Migration: extend existing audit_log for multi-entity support (idempotent)
-- Runs BEFORE indexes so new columns exist when idx_audit_entity is created
DO $$
BEGIN
    -- Drop FK constraint so invoice_id can be nullable (login/import events have no invoice)
    EXECUTE (
        SELECT 'ALTER TABLE audit_log DROP CONSTRAINT ' || constraint_name
        FROM information_schema.table_constraints
        WHERE table_name = 'audit_log' AND constraint_type = 'FOREIGN KEY'
        LIMIT 1
    );
EXCEPTION WHEN others THEN NULL;
END $$;

DO $$ BEGIN ALTER TABLE audit_log ALTER COLUMN invoice_id DROP NOT NULL; EXCEPTION WHEN others THEN NULL; END $$;
DO $$ BEGIN ALTER TABLE audit_log ALTER COLUMN field_name DROP NOT NULL;  EXCEPTION WHEN others THEN NULL; END $$;
ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS entity_type  TEXT DEFAULT 'invoice';
ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS entity_id    INTEGER;
ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS entity_label TEXT;
ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS user_id      INTEGER;
ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS user_name    TEXT;
UPDATE audit_log SET entity_type = 'invoice' WHERE entity_type IS NULL;

CREATE INDEX IF NOT EXISTS idx_audit_invoice ON audit_log(invoice_id);
CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_log(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_changed_at ON audit_log(changed_at DESC);

-- Tabela duplikatów
CREATE TABLE IF NOT EXISTS duplicate_detection (
    id SERIAL PRIMARY KEY,
    invoice_id INTEGER NOT NULL,
    duplicate_of INTEGER,
    similarity_score FLOAT,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
    FOREIGN KEY (duplicate_of) REFERENCES invoices(id) ON DELETE SET NULL
);

-- Tabela tymczasowych uploadów (staging)
CREATE TABLE IF NOT EXISTS upload_staging (
    id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    email_subject TEXT,
    email_sender TEXT,
    email_folder TEXT,
    email_date TEXT,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_staging_session ON upload_staging(session_id);
CREATE INDEX IF NOT EXISTS idx_staging_uploaded_at ON upload_staging(uploaded_at);

-- ============================================================
-- Roles & dynamic permissions (Users/Roles management module)
-- ============================================================

CREATE TABLE IF NOT EXISTS roles (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    is_protected BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS role_permissions (
    id SERIAL PRIMARY KEY,
    role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    module_name TEXT NOT NULL,
    has_access BOOLEAN DEFAULT TRUE,
    UNIQUE (role_id, module_name)
);

CREATE INDEX IF NOT EXISTS idx_role_permissions_role ON role_permissions(role_id);

-- Seed built-in roles (idempotent)
INSERT INTO roles (name, display_name, is_protected) VALUES
    ('superuser',    'Właściciel',    TRUE),
    ('admin',        'Administrator', FALSE),
    ('receptionist', 'Recepcjonista', FALSE),
    ('stylist',      'Stylista',      FALSE),
    ('accountant',   'Księgowy',      FALSE)
ON CONFLICT (name) DO NOTHING;

-- Seed role_permissions: all roles get all modules enabled (adjust before deployment)
DO $$
DECLARE
    r RECORD;
    modules TEXT[] := ARRAY['invoices','appointments','clients','employees','services','settings','reports'];
    m TEXT;
BEGIN
    FOR r IN SELECT id FROM roles LOOP
        FOREACH m IN ARRAY modules LOOP
            INSERT INTO role_permissions (role_id, module_name, has_access)
            VALUES (r.id, m, TRUE)
            ON CONFLICT (role_id, module_name) DO NOTHING;
        END LOOP;
    END LOOP;
END $$;
