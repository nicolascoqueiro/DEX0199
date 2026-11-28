-- =====================================================================
-- Dados de demonstracao (aplicados apenas na criacao do banco, a menos
-- que o servidor seja iniciado com --sem-demo).
-- Os crachas abaixo sao os mesmos que estavam fixos no firmware antigo.
-- =====================================================================

INSERT INTO usuario (uuid, nome, tipo, tag_nfc, criado_em) VALUES
    ('usr-prof-demo',    'Prof. Responsavel', 'docente', '4D:87:4E:07', datetime('now','localtime')),
    ('usr-monitor-demo', 'Monitor Lab',       'monitor', 'C0:3E:35:5C', datetime('now','localtime'));

INSERT INTO item_tipo (uuid, nome, codigo, controla_quantidade, qntd_total, qntd_disponivel, atualizado_em) VALUES
    ('tipo-arduino-uno', 'Arduino Uno',          NULL,          0, 0,   0,   datetime('now','localtime')),
    ('tipo-esp32',       'ESP32 DevKit',         NULL,          0, 0,   0,   datetime('now','localtime')),
    ('tipo-protoboard',  'Protoboard 830 pts',   NULL,          0, 0,   0,   datetime('now','localtime')),
    ('tipo-multimetro',  'Multimetro',           NULL,          0, 0,   0,   datetime('now','localtime')),
    ('tipo-jumpers',     'Jumpers (unid.)',      'DEX-CX-JUMP', 1, 200, 200, datetime('now','localtime')),
    ('tipo-resistores',  'Resistores (unid.)',   'DEX-CX-RES',  1, 500, 500, datetime('now','localtime'));

INSERT INTO item_fisico (uuid, item_tipo_id, rotulo, qr_code, criado_em, atualizado_em) VALUES
    ('item-demo-1', 1, 'Arduino Uno #1',  'DEX-0001', datetime('now','localtime'), datetime('now','localtime')),
    ('item-demo-2', 1, 'Arduino Uno #2',  'DEX-0002', datetime('now','localtime'), datetime('now','localtime')),
    ('item-demo-3', 2, 'ESP32 DevKit #1', 'DEX-0003', datetime('now','localtime'), datetime('now','localtime')),
    ('item-demo-4', 3, 'Protoboard 830 pts #1', 'DEX-0004', datetime('now','localtime'), datetime('now','localtime')),
    ('item-demo-5', 4, 'Multimetro #1',   'DEX-0005', datetime('now','localtime'), datetime('now','localtime'));
