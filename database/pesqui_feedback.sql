CREATE TABLE pesquisa (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,
    titulo TEXT NOT NULL,
    experiencia_id INTEGER REFERENCES experiencia(id),
    ativa INTEGER NOT NULL DEFAULT 1 CHECK (ativa IN (0,1)),
    criada_em TEXT NOT NULL
);

CREATE TABLE pesquisa_opcao (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pesquisa_id INTEGER NOT NULL REFERENCES pesquisa(id),
    rotulo TEXT NOT NULL,
    valor INTEGER NOT NULL
);

CREATE TABLE feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,
    pesquisa_id INTEGER NOT NULL REFERENCES pesquisa(id),
    usuario_id INTEGER NOT NULL REFERENCES usuario(id),
    experiencia_id INTEGER NOT NULL REFERENCES experiencia(id),
    opcao_id INTEGER REFERENCES pesquisa_opcao(id),
    comentario TEXT,
    data TEXT NOT NULL,
    enviado INTEGER NOT NULL DEFAULT 0 CHECK (enviado IN (0,1)),
    UNIQUE(experiencia_id, usuario_id)   -- um feedback por professor por experiência
);
