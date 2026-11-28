-- =====================================================================
-- 10 - Movimentacao de itens controlados por quantidade
-- (ocorrencias por quantidade atualizam o estoque via trigger da tabela
--  ocorrencia, por isso nao ha tipos 'ocorrencia_*' aqui)
-- =====================================================================

CREATE TABLE movimentacao_quantidade (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,
    item_tipo_id INTEGER NOT NULL REFERENCES item_tipo(id),
    tipo TEXT NOT NULL CHECK (tipo IN ('emprestimo','devolucao','ajuste_inventario')),
    quantidade INTEGER NOT NULL CHECK (quantidade >= 0),
    modalidade TEXT CHECK (modalidade IN ('bancada','casa') OR modalidade IS NULL),
    usuario_id INTEGER NOT NULL REFERENCES usuario(id),
    autorizador_id INTEGER REFERENCES usuario(id),
    experiencia_id INTEGER REFERENCES experiencia(id),
    data TEXT NOT NULL,
    relogio_confiavel INTEGER NOT NULL DEFAULT 1 CHECK (relogio_confiavel IN (0,1)),
    observacao TEXT,
    CHECK (quantidade > 0 OR tipo = 'ajuste_inventario')
);
