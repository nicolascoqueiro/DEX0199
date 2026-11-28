-- =====================================================================
-- 22 - Validacao do encerramento de experiencia (aula)
-- =====================================================================

CREATE TRIGGER trg_experiencia_encerramento_valida
BEFORE UPDATE OF status ON experiencia
WHEN NEW.status = 'encerrada' AND OLD.status = 'aberta'
BEGIN
    SELECT RAISE(ABORT, 'Decisão de encerramento não registrada')
    WHERE NEW.decisao_encerramento IS NULL;

    SELECT RAISE(ABORT, 'Experiência tem itens em aberto; devolva ou registre pendência')
    WHERE NEW.decisao_encerramento = 'sem_pendencia'
      AND (SELECT COUNT(*) FROM emprestimo_aberto WHERE experiencia_id = NEW.id) > 0;

    SELECT RAISE(ABORT, 'Feedback é obrigatório para encerrar a experiência')
    WHERE (SELECT COUNT(*) FROM feedback WHERE experiencia_id = NEW.id) = 0;
END;
