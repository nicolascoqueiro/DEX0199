-- =====================================================================
-- 30 - Indices
-- =====================================================================

CREATE INDEX idx_item_fisico_estado ON item_fisico(estado);
CREATE INDEX idx_item_fisico_tipo ON item_fisico(item_tipo_id);
CREATE INDEX idx_registro_data ON registro(data);
CREATE INDEX idx_registro_tipo ON registro(tipo);
CREATE INDEX idx_registro_item ON registro(item_fisico_id);
CREATE INDEX idx_registro_experiencia ON registro(experiencia_id);
CREATE INDEX idx_registro_inventario ON registro(inventario_sessao_id);
CREATE INDEX idx_ocorrencia_status ON ocorrencia(status_resolucao);
CREATE INDEX idx_ocorrencia_item ON ocorrencia(item_fisico_id);
CREATE INDEX idx_emprestimo_experiencia ON emprestimo_aberto(experiencia_id);
CREATE INDEX idx_experiencia_status ON experiencia(status);
CREATE INDEX idx_sessao_usuario ON sessao(usuario_id);
CREATE INDEX idx_auditoria_enviado ON auditoria(enviado_syslog);
CREATE INDEX idx_auditoria_alerta ON auditoria(alerta_central);
CREATE INDEX idx_sync_fila_pendente ON sync_fila(tentativas);
CREATE INDEX idx_leitura_pendente ON leitura(consumida, id);
