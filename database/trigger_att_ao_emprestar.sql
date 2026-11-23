CREATE TRIGGER trg_emprestimo_atualiza_estado
AFTER INSERT ON emprestimo_aberto
BEGIN
    UPDATE item_fisico SET estado = 'emprestado', atualizado_em = NEW.data_emprestimo
    WHERE id = NEW.item_fisico_id;
END;
