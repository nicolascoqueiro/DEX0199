-- =====================================================================
-- 09 - Emprestimos em aberto de itens individuais
-- Uma linha por item emprestado; e apagada na devolucao (o historico
-- permanece na tabela registro).
--   modalidade 'bancada' -> uso no laboratorio durante a aula (exige aula aberta)
--   modalidade 'casa'    -> item levado para fora do laboratorio (com prazo)
-- =====================================================================

CREATE TABLE emprestimo_aberto (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_fisico_id INTEGER NOT NULL UNIQUE REFERENCES item_fisico(id),
    usuario_id INTEGER NOT NULL REFERENCES usuario(id),
    autorizador_id INTEGER REFERENCES usuario(id),     -- NULL = monitor sem autorizacao
    experiencia_id INTEGER REFERENCES experiencia(id),
    modalidade TEXT NOT NULL CHECK (modalidade IN ('bancada','casa')),
    registro_emprestimo_id INTEGER NOT NULL REFERENCES registro(id),
    data_emprestimo TEXT NOT NULL,
    prazo_devolucao TEXT,
    relogio_confiavel INTEGER NOT NULL DEFAULT 1 CHECK (relogio_confiavel IN (0,1))
);
