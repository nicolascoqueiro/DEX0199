CREATE TRIGGER trg_movimentacao_quantidade_atualiza_tipo
AFTER INSERT ON movimentacao_quantidade
BEGIN
    UPDATE item_tipo
    SET qntd_disponivel = CASE NEW.tipo
        WHEN 'emprestimo' THEN qntd_disponivel - NEW.quantidade
        WHEN 'devolucao' THEN qntd_disponivel + NEW.quantidade
        WHEN 'ocorrencia_danificado' THEN qntd_disponivel - NEW.quantidade
        WHEN 'ocorrencia_perdido' THEN qntd_disponivel - NEW.quantidade
        WHEN 'ocorrencia_encontrado' THEN qntd_disponivel + NEW.quantidade
        WHEN 'ajuste_inventario' THEN NEW.quantidade
        ELSE qntd_disponivel
    END,
    atualizado_em = NEW.data
    WHERE id = NEW.item_tipo_id;
END;
