CREATE TABLE movimentacao_quantidade (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,
    item_tipo_id INTEGER NOT NULL REFERENCES item_tipo(id),
    tipo TEXT NOT NULL CHECK (tipo IN (
        'emprestimo','devolucao',
        'ocorrencia_danificado','ocorrencia_perdido','ocorrencia_encontrado',
        'ajuste_inventario'
    )),
    quantidade INTEGER NOT NULL CHECK (quantidade > 0),
    usuario_id INTEGER NOT NULL REFERENCES usuario(id),
    autorizador_id INTEGER REFERENCES usuario(id),
    experiencia_id INTEGER REFERENCES experiencia(id),
    ocorrencia_id INTEGER REFERENCES ocorrencia(id),
    data TEXT NOT NULL,
    relogio_confiavel INTEGER NOT NULL DEFAULT 1 CHECK (relogio_confiavel IN (0,1)),
    observacao TEXT
);
