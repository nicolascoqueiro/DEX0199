CREATE TRIGGER trg_ocorrencia_quantidade_atualiza_tipo
AFTER INSERT ON ocorrencia
WHEN NEW.item_tipo_id IS NOT NULL
BEGIN
    UPDATE item_tipo
    SET qntd_disponivel = CASE NEW.tipo
        WHEN 'danificado' THEN qntd_disponivel - NEW.quantidade
        WHEN 'perdido' THEN qntd_disponivel - NEW.quantidade
        WHEN 'furto' THEN qntd_disponivel - NEW.quantidade
        WHEN 'encontrado' THEN qntd_disponivel + NEW.quantidade
        ELSE qntd_disponivel
    END,
    atualizado_em = NEW.data
    WHERE id = NEW.item_tipo_id;
END;
