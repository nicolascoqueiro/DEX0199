-- =====================================================================
-- 03 - Experiencias (aulas / atividades pedagogicas)
-- Um docente abre a aula no terminal; emprestimos de BANCADA ficam
-- vinculados a ela. Para encerrar: decisao sobre pendencias + feedback.
-- =====================================================================

CREATE TABLE experiencia (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,
    nome TEXT NOT NULL,                   -- "Prof. Joao - 2026-11-28 14h"
    docente_gerador_id INTEGER NOT NULL REFERENCES usuario(id),
    escola_id INTEGER NOT NULL DEFAULT 1 REFERENCES escola(id),
    data_inicio TEXT NOT NULL,
    data_fim TEXT,
    status TEXT NOT NULL DEFAULT 'aberta'
        CHECK (status IN ('aberta','encerrada','cancelada')),
    qntd_itens_abertos INTEGER NOT NULL DEFAULT 0 CHECK (qntd_itens_abertos >= 0),
    -- sem_pendencia  : todos os itens devolvidos
    -- devolver_depois: itens continuam emprestados (pendencia aparece no painel)
    -- com_pendencia  : itens nao devolvidos registrados como ocorrencia 'perdido'
    decisao_encerramento TEXT
        CHECK (decisao_encerramento IN ('sem_pendencia','devolver_depois','com_pendencia')
               OR decisao_encerramento IS NULL),
    criado_em TEXT NOT NULL
);

CREATE TABLE experiencia_docente (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    experiencia_id INTEGER NOT NULL REFERENCES experiencia(id),
    usuario_id INTEGER NOT NULL REFERENCES usuario(id),
    papel TEXT NOT NULL DEFAULT 'responsavel'
        CHECK (papel IN ('responsavel','monitor','apoio')),
    UNIQUE(experiencia_id, usuario_id)
);
