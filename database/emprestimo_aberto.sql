CREATE TABLE emprestimo_aberto (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_fisico_id INTEGER NOT NULL UNIQUE REFERENCES item_fisico(id),
    usuario_id INTEGER NOT NULL REFERENCES usuario(id),
    autorizador_id INTEGER NOT NULL REFERENCES usuario(id),
    experiencia_id INTEGER NOT NULL REFERENCES experiencia(id),
    registro_emprestimo_id INTEGER NOT NULL,
    data_emprestimo TEXT NOT NULL,
    relogio_confiavel INTEGER NOT NULL DEFAULT 1 CHECK (relogio_confiavel IN (0,1))
);
