-- =====================================================================
-- 23 - Movimentacao por quantidade atualiza o estoque do tipo
-- =====================================================================

CREATE TRIGGER trg_movimentacao_quantidade_valida
BEFORE INSERT ON movimentacao_quantidade
BEGIN
    SELECT RAISE(ABORT, 'Quantidade indisponível em estoque')
    WHERE NEW.tipo = 'emprestimo'
      AND (SELECT qntd_disponivel FROM item_tipo WHERE id = NEW.item_tipo_id) < NEW.quantidade;

    SELECT RAISE(ABORT, 'Devolução excede a quantidade total cadastrada')
    WHERE NEW.tipo = 'devolucao'
      AND (SELECT qntd_disponivel + NEW.quantidade - qntd_total FROM item_tipo WHERE id = NEW.item_tipo_id) > 0;

    SELECT RAISE(ABORT, 'Ajuste excede a quantidade total cadastrada')
    WHERE NEW.tipo = 'ajuste_inventario'
      AND (SELECT qntd_total FROM item_tipo WHERE id = NEW.item_tipo_id) < NEW.quantidade;
END;

CREATE TRIGGER trg_movimentacao_quantidade_atualiza_tipo
AFTER INSERT ON movimentacao_quantidade
BEGIN
    UPDATE item_tipo
    SET qntd_disponivel = CASE NEW.tipo
        WHEN 'emprestimo' THEN qntd_disponivel - NEW.quantidade
        WHEN 'devolucao' THEN qntd_disponivel + NEW.quantidade
        WHEN 'ajuste_inventario' THEN NEW.quantidade
        ELSE qntd_disponivel
    END,
    atualizado_em = NEW.data
    WHERE id = NEW.item_tipo_id;
END;
