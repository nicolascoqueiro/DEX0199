CREATE TRIGGER trg_ocorrencia_individual_atualiza_item
AFTER INSERT ON ocorrencia
WHEN NEW.item_fisico_id IS NOT NULL
BEGIN
    UPDATE item_fisico
    SET estado = CASE NEW.tipo
        WHEN 'danificado' THEN 'manutencao'
        WHEN 'perdido' THEN 'perdido'
        WHEN 'encontrado' THEN 'disponivel'
        WHEN 'furto' THEN 'perdido'
        ELSE estado
    END,
    atualizado_em = NEW.data
    WHERE id = NEW.item_fisico_id;
END;
