-- =====================================================================
-- 01 - Configuracao local (chave-valor) e escola
-- Todas as datas do banco sao gravadas em HORARIO LOCAL no formato
-- 'YYYY-MM-DD HH:MM:SS' (compativel com datetime('now','localtime')).
-- =====================================================================

CREATE TABLE config (
    chave TEXT PRIMARY KEY,
    valor TEXT NOT NULL,
    atualizado_em TEXT NOT NULL
);

-- Escola / laboratorio (o MVP opera com uma unica escola, id = 1)
CREATE TABLE escola (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,
    nome TEXT NOT NULL,
    codigo TEXT UNIQUE NOT NULL,
    sincronizado_em TEXT
);
