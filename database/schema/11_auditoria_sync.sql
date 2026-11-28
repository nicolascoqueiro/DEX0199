-- =====================================================================
-- 11 - Auditoria e sincronizacao (sync reservado para a fase multi-escola)
-- =====================================================================

CREATE TABLE auditoria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT NOT NULL,
    usuario_id INTEGER REFERENCES usuario(id),
    evento TEXT NOT NULL,
    detalhe TEXT,
    relogio_confiavel INTEGER NOT NULL DEFAULT 1 CHECK (relogio_confiavel IN (0,1)),
    enviado_syslog INTEGER NOT NULL DEFAULT 0 CHECK (enviado_syslog IN (0,1)),
    alerta_central INTEGER NOT NULL DEFAULT 0 CHECK (alerta_central IN (0,1))
);

CREATE TABLE sync_estado (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entidade TEXT NOT NULL UNIQUE,
    ultima_sync TEXT,
    cursor_remoto TEXT
);

CREATE TABLE sync_fila (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entidade TEXT NOT NULL,
    operacao TEXT NOT NULL CHECK (operacao IN ('insert','update','delete','alerta')),
    payload TEXT NOT NULL,
    criado_em TEXT NOT NULL,
    tentativas INTEGER NOT NULL DEFAULT 0,
    ultimo_erro TEXT
);
