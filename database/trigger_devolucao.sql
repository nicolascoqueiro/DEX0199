CREATE TRIGGER trg_devolucao_atualiza_estado
AFTER DELETE ON emprestimo_aberto
BEGIN
    UPDATE item_fisico SET estado = 'disponivel', atualizado_em = datetime('now')
    WHERE id = OLD.item_fisico_id;
END;
