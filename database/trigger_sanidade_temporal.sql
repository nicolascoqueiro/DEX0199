CREATE TRIGGER trg_data_sanidade_registro
BEFORE INSERT ON registro
WHEN NEW.data > datetime('now', '+1 day')
  OR NEW.data < datetime('now', '-7 days')
BEGIN
    SELECT RAISE(ABORT, 'Data fora da janela de sanidade — verifique RTC/NTP');
END;

CREATE TRIGGER trg_data_sanidade_auditoria
BEFORE INSERT ON auditoria
WHEN NEW.data > datetime('now', '+1 day')
  OR NEW.data < datetime('now', '-7 days')
BEGIN
    SELECT RAISE(ABORT, 'Data fora da janela de sanidade — verifique RTC/NTP');
END;
