CREATE TRIGGER trg_emprestimo_so_se_disponivel
BEFORE INSERT ON emprestimo_aberto
BEGIN
    SELECT CASE
        WHEN (SELECT estado FROM item_fisico WHERE id = NEW.item_fisico_id) <> 'disponivel'
        THEN RAISE(ABORT, 'Item não está disponível para empréstimo')
    END;
END;
