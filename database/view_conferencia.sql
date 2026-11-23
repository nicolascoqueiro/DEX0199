-- Conferência de inventário (seção 7)
CREATE VIEW v_inventario_conferencia AS
SELECT
    i.id AS item_fisico_id,
    i.tag_nfc,
    i.qr_code,
    t.nome AS tipo_nome,
    i.estado,
    CASE WHEN r.id IS NOT NULL THEN 'lido' ELSE 'pendente_leitura' END AS leitura,
    CASE WHEN e.id IS NOT NULL THEN 'em_emprestimo' ELSE NULL END AS pendencia_emprestimo,
    CASE WHEN o.id IS NOT NULL THEN 'com_ocorrencia' ELSE NULL END AS pendencia_ocorrencia
FROM item_fisico i
JOIN item_tipo t ON t.id = i.item_tipo_id
LEFT JOIN registro r
    ON r.item_fisico_id = i.id
    AND r.tipo = 'inventario_leitura'
    AND r.inventario_sessao_id = (
        SELECT id FROM inventario_sessao WHERE status = 'aberta' ORDER BY id DESC LIMIT 1
    )
LEFT JOIN emprestimo_aberto e ON e.item_fisico_id = i.id
LEFT JOIN ocorrencia o ON o.item_fisico_id = i.id AND o.status_resolucao != 'resolvida'
WHERE i.escola_id = (SELECT CAST(valor AS INTEGER) FROM config WHERE chave = 'escola_id')
  AND i.estado NOT IN ('perdido','removido');

-- Histórico unificado (para a tela de consulta do quadro)
CREATE VIEW v_historico AS
SELECT
    r.id AS registro_id,
    r.uuid,
    r.tipo,
    r.data,
    r.item_fisico_id,
    r.item_tipo_id,
    r.quantidade,
    u.nome AS operador,
    a.nome AS autorizador,
    exp.nome AS experiencia,
    r.observacao
FROM registro r
LEFT JOIN usuario u ON u.id = r.usuario_id
LEFT JOIN usuario a ON a.id = r.autorizador_id
LEFT JOIN experiencia exp ON exp.id = r.experiencia_id
ORDER BY r.data DESC;

-- Pendências por experiência (para a tela de encerramento)
CREATE VIEW v_pendencias_experiencia AS
SELECT
    e.experiencia_id,
    e.item_fisico_id,
    i.tag_nfc,
    t.nome AS tipo_nome,
    e.data_emprestimo,
    e.usuario_id,
    e.autorizador_id
FROM emprestimo_aberto e
JOIN item_fisico i ON i.id = e.item_fisico_id
JOIN item_tipo t ON t.id = i.item_tipo_id;
