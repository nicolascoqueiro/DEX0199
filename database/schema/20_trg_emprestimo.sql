-- =====================================================================
-- 20 - Triggers de emprestimo / devolucao de itens individuais
-- =====================================================================

-- So empresta item que esta 'disponivel'
CREATE TRIGGER trg_emprestimo_so_se_disponivel
BEFORE INSERT ON emprestimo_aberto
BEGIN
    SELECT RAISE(ABORT, 'Item não está disponível para empréstimo')
    WHERE (SELECT estado FROM item_fisico WHERE id = NEW.item_fisico_id) <> 'disponivel';
END;

-- Ao emprestar: item passa a 'emprestado'
CREATE TRIGGER trg_emprestimo_atualiza_estado
AFTER INSERT ON emprestimo_aberto
BEGIN
    UPDATE item_fisico SET estado = 'emprestado', atualizado_em = NEW.data_emprestimo
    WHERE id = NEW.item_fisico_id;
END;

-- Ao devolver (DELETE do emprestimo aberto): item volta a 'disponivel'
-- (ou vira 'removido' se havia sido marcado como removido_pendente)
CREATE TRIGGER trg_devolucao_atualiza_estado
AFTER DELETE ON emprestimo_aberto
BEGIN
    UPDATE item_fisico
    SET estado = CASE WHEN estado = 'removido_pendente' THEN 'removido' ELSE 'disponivel' END,
        atualizado_em = datetime('now','localtime')
    WHERE id = OLD.item_fisico_id;
END;

-- Contador de itens em aberto por experiencia
CREATE TRIGGER trg_emprestimo_incrementa_qntd
AFTER INSERT ON emprestimo_aberto
WHEN NEW.experiencia_id IS NOT NULL
BEGIN
    UPDATE experiencia
    SET qntd_itens_abertos = qntd_itens_abertos + 1
    WHERE id = NEW.experiencia_id;
END;

CREATE TRIGGER trg_devolucao_decrementa_qntd
AFTER DELETE ON emprestimo_aberto
WHEN OLD.experiencia_id IS NOT NULL
BEGIN
    UPDATE experiencia
    SET qntd_itens_abertos = MAX(qntd_itens_abertos - 1, 0)
    WHERE id = OLD.experiencia_id;
END;

-- Item com emprestimo aberto nao pode ser apagado fisicamente
CREATE TRIGGER trg_bloqueia_delete_item_emprestado
BEFORE DELETE ON item_fisico
WHEN (SELECT COUNT(*) FROM emprestimo_aberto WHERE item_fisico_id = OLD.id) > 0
BEGIN
    SELECT RAISE(ABORT, 'Item em empréstimo aberto não pode ser removido; marque removido_pendente');
END;
