CREATE TRIGGER trg_alerta_sem_autorizacao
AFTER INSERT ON registro
WHEN NEW.tipo = 'emprestimo_experiencia'
  AND NEW.autorizador_id IS NULL
  AND (SELECT tipo FROM usuario WHERE id = NEW.usuario_id) = 'monitor'
BEGIN
    INSERT INTO auditoria (data, usuario_id, evento, detalhe, alerta_central)
    VALUES (
        NEW.data,
        NEW.usuario_id,
        'emprestimo_sem_autorizacao',
        json_object('registro_id', NEW.id, 'item_fisico_id', NEW.item_fisico_id, 'experiencia_id', NEW.experiencia_id),
        1
    );
END;
