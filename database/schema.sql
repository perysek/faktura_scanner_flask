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
    invoice_id INTEGER NOT NULL,
    action TEXT DEFAULT 'UPDATE',
    field_name TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_audit_invoice ON audit_log(invoice_id);

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
CREATE INDEX IF NOT EXISTS idx_staging_uploaded_at ON upload_staging(uploaded_at)
