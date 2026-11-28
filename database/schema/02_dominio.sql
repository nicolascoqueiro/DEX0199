-- =====================================================================
-- 02 - Dominio: tipos de item, itens fisicos, usuarios e permissoes
-- =====================================================================

-- Tipos de item (categoria). Dois modos de controle:
--   controla_quantidade = 0 -> cada unidade e um item_fisico com tag NFC/QR propria
--   controla_quantidade = 1 -> controle por quantidade (ex.: caixa de resistores),
--                              identificada pelo "codigo" (QR/NFC colado na caixa)
CREATE TABLE item_tipo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,
    nome TEXT NOT NULL,
    codigo TEXT UNIQUE,
    controla_quantidade INTEGER NOT NULL DEFAULT 0 CHECK (controla_quantidade IN (0,1)),
    qntd_total INTEGER NOT NULL DEFAULT 0 CHECK (qntd_total >= 0),
    qntd_disponivel INTEGER NOT NULL DEFAULT 0 CHECK (qntd_disponivel >= 0),
    ativo INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0,1)),
    escola_id INTEGER NOT NULL DEFAULT 1 REFERENCES escola(id),
    atualizado_em TEXT NOT NULL,
    CHECK (qntd_disponivel <= qntd_total)
);

-- Itens fisicos individualmente rastreaveis (tag NFC e/ou QR unico)
CREATE TABLE item_fisico (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,
    item_tipo_id INTEGER NOT NULL REFERENCES item_tipo(id),
    rotulo TEXT NOT NULL,                 -- ex.: "Arduino Uno #3"
    tag_nfc TEXT UNIQUE,
    qr_code TEXT UNIQUE,
    estado TEXT NOT NULL DEFAULT 'disponivel'
        CHECK (estado IN ('disponivel','emprestado','manutencao','perdido','removido','removido_pendente')),
    observacao TEXT,
    escola_id INTEGER NOT NULL DEFAULT 1 REFERENCES escola(id),
    criado_em TEXT NOT NULL,
    atualizado_em TEXT NOT NULL,
    CHECK (tag_nfc IS NOT NULL OR qr_code IS NOT NULL)
);

-- Usuarios (docentes, monitores e administradores) - todos com cracha NFC
CREATE TABLE usuario (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,
    nome TEXT NOT NULL,
    tipo TEXT NOT NULL CHECK (tipo IN ('docente','monitor','admin')),
    tag_nfc TEXT UNIQUE NOT NULL,
    ativo INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0,1)),
    escola_id INTEGER NOT NULL DEFAULT 1 REFERENCES escola(id),
    criado_em TEXT NOT NULL
);

-- Permissoes discricionarias (reservado para fases futuras)
CREATE TABLE permissao (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL REFERENCES usuario(id),
    chave TEXT NOT NULL,
    concedida_por INTEGER REFERENCES usuario(id),
    concedida_em TEXT NOT NULL,
    revogada_em TEXT,
    UNIQUE(usuario_id, chave)
);
