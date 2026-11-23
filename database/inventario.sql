CREATE TABLE inventario_sessao (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,
    escola_id INTEGER NOT NULL REFERENCES escola(id),
    usuario_id INTEGER NOT NULL REFERENCES usuario(id),
    iniciada_em TEXT NOT NULL,
    encerrada_em TEXT,
    status TEXT NOT NULL DEFAULT 'aberta'
        CHECK (status IN ('aberta','encerrada','cancelada'))
);
