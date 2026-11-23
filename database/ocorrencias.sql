CREATE TABLE ocorrencia (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,
    item_fisico_id INTEGER REFERENCES item_fisico(id),
    item_tipo_id INTEGER REFERENCES item_tipo(id),
    quantidade INTEGER NOT NULL DEFAULT 1 CHECK (quantidade > 0),
    quantidade_resolvida INTEGER NOT NULL DEFAULT 0
        CHECK (quantidade_resolvida >= 0 AND quantidade_resolvida <= quantidade),
    status_resolucao TEXT NOT NULL DEFAULT 'aberta'
        CHECK (status_resolucao IN ('aberta','parcial','resolvida')),
    experiencia_id INTEGER REFERENCES experiencia(id),
    tipo TEXT NOT NULL CHECK (tipo IN ('danificado','perdido','encontrado','furto','outro')),
    descricao TEXT,
    registrado_por INTEGER NOT NULL REFERENCES usuario(id),
    data TEXT NOT NULL,
    relogio_confiavel INTEGER NOT NULL DEFAULT 1 CHECK (relogio_confiavel IN (0,1)),
    CHECK (
        (item_fisico_id IS NOT NULL AND item_tipo_id IS NULL) OR
        (item_fisico_id IS NULL AND item_tipo_id IS NOT NULL)
    )
);
