CREATE TRIGGER trg_experiencia_encerramento_valida
BEFORE UPDATE OF status ON experiencia
WHEN NEW.status = 'encerrada'
BEGIN
    SELECT CASE
        WHEN (SELECT COUNT(*) FROM emprestimo_aberto WHERE experiencia_id = NEW.id) > 0
        THEN RAISE(ABORT, 'Experiência tem itens em aberto; devolva ou registre pendência')
    END;
    SELECT CASE
        WHEN NEW.decisao_encerramento IS NULL
        THEN RAISE(ABORT, 'Decisão de encerramento não registrada')
    END;
    SELECT CASE
        WHEN (SELECT COUNT(*) FROM feedback WHERE experiencia_id = NEW.id) = 0
        THEN RAISE(ABORT, 'Feedback é obrigatório para encerrar a experiência')
    END;
END;
