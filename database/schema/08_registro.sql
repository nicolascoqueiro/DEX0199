-- =====================================================================
-- 08 - Registro unico (log imutavel de eventos de itens)
-- =====================================================================

CREATE TABLE registro (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,
    tipo TEXT NOT NULL CHECK (tipo IN (
        'cadastro','remocao',
        'emprestimo','devolucao',
        'ocorrencia','inventario_leitura','inventario_faltante',
        'feedback'
    )),
    data TEXT NOT NULL,
    item_fisico_id INTEGER REFERENCES item_fisico(id),
    item_tipo_id INTEGER REFERENCES item_tipo(id),
    quantidade INTEGER,
    modalidade TEXT CHECK (modalidade IN ('bancada','casa') OR modalidade IS NULL),
    usuario_id INTEGER NOT NULL REFERENCES usuario(id),
    autorizador_id INTEGER REFERENCES usuario(id),
    experiencia_id INTEGER REFERENCES experiencia(id),
    ocorrencia_id INTEGER REFERENCES ocorrencia(id),
    inventario_sessao_id INTEGER REFERENCES inventario_sessao(id),
    feedback_id INTEGER REFERENCES feedback(id),
    leitor TEXT CHECK (leitor IN ('qr','nfc','manual')),
    dispositivo_id TEXT,
    relogio_confiavel INTEGER NOT NULL DEFAULT 1 CHECK (relogio_confiavel IN (0,1)),
    observacao TEXT,
    CHECK (
        (item_fisico_id IS NOT NULL AND item_tipo_id IS NULL) OR
        (item_fisico_id IS NULL AND item_tipo_id IS NOT NULL) OR
        (item_fisico_id IS NULL AND item_tipo_id IS NULL AND tipo IN ('feedback'))
    )
);
