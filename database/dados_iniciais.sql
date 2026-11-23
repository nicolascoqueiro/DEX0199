-- Configuração local do token (preenchida no provisionamento)
INSERT INTO config (chave, valor, atualizado_em) VALUES
    ('escola_id', '0', datetime('now')),
    ('schema_version', '1', datetime('now')),
    ('ultima_sync', '', datetime('now')),
    ('ultima_sync_ntp', '', datetime('now')),
    ('ttl_sessao_minutos', '15', datetime('now')),
    ('ttl_autorizacao_horas', '2', datetime('now')),
    ('janela_relogio_horas', '24', datetime('now'));

-- Pesquisa padrão de humor pós-aula (pode vir do servidor)
INSERT INTO pesquisa (uuid, titulo, ativa, criada_em) VALUES
    ('pesquisa-humor-padrao', 'Como foi a aula hoje?', 1, datetime('now'));

INSERT INTO pesquisa_opcao (pesquisa_id, rotulo, valor) VALUES
    (1, 'Muito ruim', 1),
    (1, 'Ruim', 2),
    (1, 'Neutro', 3),
    (1, 'Bom', 4),
    (1, 'Muito bom', 5);
