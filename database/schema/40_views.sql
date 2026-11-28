-- =====================================================================
-- 40 - Views
-- =====================================================================

-- Conferencia de inventario (sessao aberta mais recente)
CREATE VIEW v_inventario_conferencia AS
SELECT
    i.id AS item_fisico_id,
    i.rotulo,
    i.tag_nfc,
    i.qr_code,
    t.nome AS tipo_nome,
    i.estado,
    CASE WHEN EXISTS (
        SELECT 1 FROM registro r
        WHERE r.item_fisico_id = i.id
          AND r.tipo = 'inventario_leitura'
          AND r.inventario_sessao_id = (
              SELECT id FROM inventario_sessao WHERE status = 'aberta' ORDER BY id DESC LIMIT 1)
    ) THEN 'lido' ELSE 'pendente_leitura' END AS leitura,
    CASE WHEN EXISTS (SELECT 1 FROM emprestimo_aberto e WHERE e.item_fisico_id = i.id)
         THEN 'em_emprestimo' END AS pendencia_emprestimo,
    CASE WHEN EXISTS (SELECT 1 FROM ocorrencia o
                      WHERE o.item_fisico_id = i.id AND o.status_resolucao <> 'resolvida')
         THEN 'com_ocorrencia' END AS pendencia_ocorrencia
FROM item_fisico i
JOIN item_tipo t ON t.id = i.item_tipo_id
WHERE i.escola_id = (SELECT CAST(valor AS INTEGER) FROM config WHERE chave = 'escola_id')
  AND i.estado NOT IN ('perdido','removido');

-- Historico unificado
CREATE VIEW v_historico AS
SELECT
    r.id AS registro_id,
    r.uuid,
    r.tipo,
    r.data,
    r.item_fisico_id,
    r.item_tipo_id,
    COALESCE(i.rotulo, t.nome) AS item,
    r.quantidade,
    r.modalidade,
    r.leitor,
    u.nome AS operador,
    a.nome AS autorizador,
    exp.nome AS experiencia,
    r.observacao
FROM registro r
LEFT JOIN item_fisico i ON i.id = r.item_fisico_id
LEFT JOIN item_tipo t ON t.id = r.item_tipo_id
LEFT JOIN usuario u ON u.id = r.usuario_id
LEFT JOIN usuario a ON a.id = r.autorizador_id
LEFT JOIN experiencia exp ON exp.id = r.experiencia_id
ORDER BY r.data DESC, r.id DESC;

-- Pendencias por experiencia (tela de encerramento de aula)
CREATE VIEW v_pendencias_experiencia AS
SELECT
    e.experiencia_id,
    e.item_fisico_id,
    i.rotulo,
    i.tag_nfc,
    i.qr_code,
    t.nome AS tipo_nome,
    e.modalidade,
    e.data_emprestimo,
    e.usuario_id,
    e.autorizador_id
FROM emprestimo_aberto e
JOIN item_fisico i ON i.id = e.item_fisico_id
JOIN item_tipo t ON t.id = i.item_tipo_id;

-- Emprestimos em aberto com nomes (painel)
CREATE VIEW v_emprestimos_abertos AS
SELECT
    e.id,
    e.item_fisico_id,
    i.rotulo,
    t.nome AS tipo_nome,
    e.modalidade,
    e.data_emprestimo,
    e.prazo_devolucao,
    CASE WHEN e.prazo_devolucao IS NOT NULL
              AND e.prazo_devolucao < datetime('now','localtime') THEN 1 ELSE 0 END AS atrasado,
    u.nome AS responsavel,
    a.nome AS autorizador,
    exp.nome AS experiencia,
    exp.status AS experiencia_status
FROM emprestimo_aberto e
JOIN item_fisico i ON i.id = e.item_fisico_id
JOIN item_tipo t ON t.id = i.item_tipo_id
JOIN usuario u ON u.id = e.usuario_id
LEFT JOIN usuario a ON a.id = e.autorizador_id
LEFT JOIN experiencia exp ON exp.id = e.experiencia_id;
