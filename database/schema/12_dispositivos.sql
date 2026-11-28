-- =====================================================================
-- 12 - Dispositivos (ESP32 CYD / ESP32-S3) e fila de leituras
-- A estacao optica (S3) publica cada QR lido em "leitura"; o terminal
-- (CYD) consome a leitura mais recente nao consumida.
-- =====================================================================

CREATE TABLE dispositivo (
    id TEXT PRIMARY KEY,                  -- ex.: 'cyd-01', 's3-01'
    tipo TEXT NOT NULL CHECK (tipo IN ('kiosk','camera','outro')),
    ip TEXT,
    firmware TEXT,
    ultimo_contato TEXT NOT NULL,
    info TEXT                             -- JSON livre (RSSI, heap, etc.)
);

CREATE TABLE leitura (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT NOT NULL,
    dispositivo_id TEXT,
    codigo TEXT NOT NULL,
    origem TEXT NOT NULL CHECK (origem IN ('qr','nfc','manual')),
    consumida INTEGER NOT NULL DEFAULT 0 CHECK (consumida IN (0,1)),
    consumida_em TEXT
);
