CREATE TRIGGER trg_encontro_parcial
AFTER INSERT ON ocorrencia
WHEN NEW.tipo = 'encontrado' AND NEW.item_tipo_id IS NOT NULL
BEGIN
    UPDATE ocorrencia
    SET quantidade_resolvida = MIN(quantidade, quantidade_resolvida + NEW.quantidade),
        status_resolucao = CASE
            WHEN quantidade_resolvida + NEW.quantidade >= quantidade THEN 'resolvida'
            WHEN quantidade_resolvida + NEW.quantidade > 0 THEN 'parcial'
            ELSE 'aberta'
        END
    WHERE item_tipo_id = NEW.item_tipo_id
      AND tipo = 'perdido'
      AND status_resolucao != 'resolvida'
      AND id != NEW.id;
END;
