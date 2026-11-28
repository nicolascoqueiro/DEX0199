-- =====================================================================
-- 90 - Dados iniciais obrigatorios
-- =====================================================================

INSERT INTO escola (id, uuid, nome, codigo) VALUES
    (1, 'escola-padrao', 'Laboratório Maker', 'LAB01');

INSERT INTO config (chave, valor, atualizado_em) VALUES
    ('escola_id', '1', datetime('now','localtime')),
    ('schema_version', '2', datetime('now','localtime')),
    ('ultima_sync', '', datetime('now','localtime')),
    ('ultima_sync_ntp', '', datetime('now','localtime')),
    ('ttl_sessao_minutos', '5', datetime('now','localtime')),
    ('ttl_autorizacao_horas', '2', datetime('now','localtime')),
    ('prazo_casa_dias', '7', datetime('now','localtime')),
    ('janela_relogio_horas', '24', datetime('now','localtime'));

-- Usuario tecnico usado para registrar acoes feitas pelo painel web.
-- A "tag" nao e um UID NFC valido, portanto ninguem consegue logar com ele no terminal.
INSERT INTO usuario (uuid, nome, tipo, tag_nfc, ativo, criado_em) VALUES
    ('usr-painel-web', 'Painel Web', 'admin', 'PAINEL-WEB', 1, datetime('now','localtime'));

-- Pesquisa padrao de humor pos-aula
INSERT INTO pesquisa (id, uuid, titulo, ativa, criada_em) VALUES
    (1, 'pesquisa-humor-padrao', 'Como foi a aula hoje?', 1, datetime('now','localtime'));

INSERT INTO pesquisa_opcao (pesquisa_id, rotulo, valor) VALUES
    (1, 'Muito ruim', 1),
    (1, 'Ruim', 2),
    (1, 'Neutro', 3),
    (1, 'Bom', 4),
    (1, 'Muito bom', 5);
