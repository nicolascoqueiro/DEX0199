-- Tipos de item (categoria)
CREATE TABLE item_tipo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,
    nome TEXT NOT NULL,
    qntd_total INTEGER NOT NULL DEFAULT 0 CHECK (qntd_total >= 0),
    qntd_disponivel INTEGER NOT NULL DEFAULT 0 CHECK (qntd_disponivel >= 0),
    controla_quantidade INTEGER NOT NULL DEFAULT 0 CHECK (controla_quantidade IN (0,1)),
    escola_id INTEGER NOT NULL REFERENCES escola(id),
    atualizado_em TEXT NOT NULL,
    UNIQUE(uuid, escola_id)
);

-- Itens físicos individualmente rastreáveis (tag NFC ou QR única)
CREATE TABLE item_fisico (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,
    item_tipo_id INTEGER NOT NULL REFERENCES item_tipo(id),
    tag_nfc TEXT UNIQUE,
    qr_code TEXT UNIQUE,
    estado TEXT NOT NULL DEFAULT 'disponivel'
        CHECK (estado IN ('disponivel','emprestado','manutencao','perdido','removido','removido_pendente')),
    escola_id INTEGER NOT NULL REFERENCES escola(id),
    atualizado_em TEXT NOT NULL,
    CHECK (tag_nfc IS NOT NULL OR qr_code IS NOT NULL),
    UNIQUE(uuid, escola_id)
);

-- Usuários (docentes e monitores) — todos com tag NFC
CREATE TABLE usuario (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,
    nome TEXT NOT NULL,
    tipo TEXT NOT NULL CHECK (tipo IN ('docente','monitor','admin')),
    tag_nfc TEXT UNIQUE NOT NULL,
    ativo INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0,1)),
    escola_id INTEGER NOT NULL REFERENCES escola(id),
    UNIQUE(uuid, escola_id)
);

-- Permissões discricionárias
CREATE TABLE permissao (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL REFERENCES usuario(id),
    chave TEXT NOT NULL,
    concedida_por INTEGER REFERENCES usuario(id),
    concedida_em TEXT NOT NULL,
    revogada_em TEXT,
    UNIQUE(usuario_id, chave)
);
