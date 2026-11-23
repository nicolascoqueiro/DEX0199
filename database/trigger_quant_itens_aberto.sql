CREATE TRIGGER trg_emprestimo_incrementa_qntd
AFTER INSERT ON emprestimo_aberto
BEGIN
    UPDATE experiencia
    SET qntd_itens_abertos = qntd_itens_abertos + 1
    WHERE id = NEW.experiencia_id;
END;

CREATE TRIGGER trg_devolucao_decrementa_qntd
AFTER DELETE ON emprestimo_aberto
BEGIN
    UPDATE experiencia
    SET qntd_itens_abertos = qntd_itens_abertos - 1
    WHERE id = OLD.experiencia_id;
END;
