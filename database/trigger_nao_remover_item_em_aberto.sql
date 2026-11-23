CREATE TRIGGER trg_bloqueia_delete_item_emprestado
BEFORE DELETE ON item_fisico
WHEN (SELECT COUNT(*) FROM emprestimo_aberto WHERE item_fisico_id = OLD.id) > 0
BEGIN
    SELECT RAISE(ABORT, 'Item em empréstimo aberto não pode ser removido; marque removido_pendente');
END;
