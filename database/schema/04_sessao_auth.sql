-- =====================================================================
-- 04 - Sessoes de login (TTL deslizante) e autorizacao de monitores
-- =====================================================================

-- Sessao de login no terminal. Guardamos apenas o hash SHA-256 do token.
CREATE TABLE sessao (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_hash TEXT UNIQUE NOT NULL,
    usuario_id INTEGER NOT NULL REFERENCES usuario(id),
    dispositivo_id TEXT,
    criada_em TEXT NOT NULL,
    expira_em TEXT NOT NULL,              -- renovado a cada requisicao
    revogada INTEGER NOT NULL DEFAULT 0 CHECK (revogada IN (0,1)),
    relogio_confiavel INTEGER NOT NULL DEFAULT 1 CHECK (relogio_confiavel IN (0,1))
);

-- Autorizacao de monitor por professor (valida por ttl_autorizacao_horas)
CREATE TABLE autorizacao_sessao (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,
    monitor_id INTEGER NOT NULL REFERENCES usuario(id),
    autorizador_id INTEGER NOT NULL REFERENCES usuario(id),
    experiencia_id INTEGER REFERENCES experiencia(id),
    criada_em TEXT NOT NULL,
    expira_em TEXT,                       -- NULL = sem tempo definido
    revogada INTEGER NOT NULL DEFAULT 0 CHECK (revogada IN (0,1)),
    sem_autorizacao INTEGER NOT NULL DEFAULT 0 CHECK (sem_autorizacao IN (0,1))
);
