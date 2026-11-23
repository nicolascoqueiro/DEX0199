PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- Chave-valor para configuração local do token
CREATE TABLE config (
    chave TEXT PRIMARY KEY,
    valor TEXT NOT NULL,
    atualizado_em TEXT NOT NULL
);

-- Escola (uma por token)
CREATE TABLE escola (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,
    nome TEXT NOT NULL,
    codigo TEXT UNIQUE NOT NULL,
    sincronizado_em TEXT
);
