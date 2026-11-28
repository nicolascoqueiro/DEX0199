-- =====================================================================
-- 25 - Sanidade temporal: rejeita datas absurdas (RTC/NTP desajustado)
-- Datas sao gravadas em horario local.
-- =====================================================================

CREATE TRIGGER trg_data_sanidade_registro
BEFORE INSERT ON registro
WHEN NEW.data > datetime('now','localtime','+1 day')
  OR NEW.data < datetime('now','localtime','-7 days')
BEGIN
    SELECT RAISE(ABORT, 'Data fora da janela de sanidade — verifique RTC/NTP');
END;

CREATE TRIGGER trg_data_sanidade_auditoria
BEFORE INSERT ON auditoria
WHEN NEW.data > datetime('now','localtime','+1 day')
  OR NEW.data < datetime('now','localtime','-7 days')
BEGIN
    SELECT RAISE(ABORT, 'Data fora da janela de sanidade — verifique RTC/NTP');
END;
