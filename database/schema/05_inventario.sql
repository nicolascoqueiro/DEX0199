-- =====================================================================
-- 05 - Sessoes de conferencia de inventario
-- Durante uma sessao aberta, cada leitura gera registro 'inventario_leitura'.
-- Ao encerrar, itens nao lidos geram registro 'inventario_faltante'.
-- =====================================================================

CREATE TABLE inventario_sessao (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,
    escola_id INTEGER NOT NULL DEFAULT 1 REFERENCES escola(id),
    usuario_id INTEGER NOT NULL REFERENCES usuario(id),
    iniciada_em TEXT NOT NULL,
    encerrada_em TEXT,
    status TEXT NOT NULL DEFAULT 'aberta'
        CHECK (status IN ('aberta','encerrada','cancelada')),
    total_esperado INTEGER,
    total_lido INTEGER
);
