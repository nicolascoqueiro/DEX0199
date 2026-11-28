-- =====================================================================
-- 24 - Ocorrencias: efeitos sobre itens individuais e por quantidade
-- =====================================================================

-- 'encontrado' so faz sentido para item individual que esta 'perdido'
CREATE TRIGGER trg_ocorrencia_encontrado_valida
BEFORE INSERT ON ocorrencia
WHEN NEW.tipo = 'encontrado' AND NEW.item_fisico_id IS NOT NULL
BEGIN
    SELECT RAISE(ABORT, 'Só é possível registrar como encontrado um item marcado como perdido')
    WHERE (SELECT estado FROM item_fisico WHERE id = NEW.item_fisico_id) <> 'perdido';
END;

-- Item individual com emprestimo aberto precisa ter o emprestimo encerrado
-- antes de virar manutencao/perdido (feito pela aplicacao)
CREATE TRIGGER trg_ocorrencia_exige_emprestimo_fechado
BEFORE INSERT ON ocorrencia
WHEN NEW.item_fisico_id IS NOT NULL AND NEW.tipo IN ('danificado','perdido','furto')
BEGIN
    SELECT RAISE(ABORT, 'Encerre o empréstimo aberto antes de registrar a ocorrência')
    WHERE (SELECT COUNT(*) FROM emprestimo_aberto WHERE item_fisico_id = NEW.item_fisico_id) > 0;
END;

-- Atualiza o estado do item individual
CREATE TRIGGER trg_ocorrencia_individual_atualiza_item
AFTER INSERT ON ocorrencia
WHEN NEW.item_fisico_id IS NOT NULL
BEGIN
    UPDATE item_fisico
    SET estado = CASE NEW.tipo
        WHEN 'danificado' THEN 'manutencao'
        WHEN 'perdido' THEN 'perdido'
        WHEN 'encontrado' THEN 'disponivel'
        WHEN 'furto' THEN 'perdido'
        ELSE estado
    END,
    atualizado_em = NEW.data
    WHERE id = NEW.item_fisico_id;
END;

-- Item individual encontrado resolve as ocorrencias de perda abertas
CREATE TRIGGER trg_encontro_individual
AFTER INSERT ON ocorrencia
WHEN NEW.tipo = 'encontrado' AND NEW.item_fisico_id IS NOT NULL
BEGIN
    UPDATE ocorrencia
    SET quantidade_resolvida = quantidade,
        status_resolucao = 'resolvida',
        resolvida_em = NEW.data,
        resolvida_por = NEW.registrado_por,
        resolucao = 'Item encontrado'
    WHERE item_fisico_id = NEW.item_fisico_id
      AND tipo IN ('perdido','furto')
      AND status_resolucao <> 'resolvida'
      AND id <> NEW.id;
END;

-- Atualiza o estoque de itens controlados por quantidade
CREATE TRIGGER trg_ocorrencia_quantidade_valida
BEFORE INSERT ON ocorrencia
WHEN NEW.item_tipo_id IS NOT NULL AND NEW.tipo IN ('danificado','perdido','furto')
BEGIN
    SELECT RAISE(ABORT, 'Quantidade da ocorrência maior que a disponível em estoque')
    WHERE (SELECT qntd_disponivel FROM item_tipo WHERE id = NEW.item_tipo_id) < NEW.quantidade;
END;

CREATE TRIGGER trg_ocorrencia_quantidade_atualiza_tipo
AFTER INSERT ON ocorrencia
WHEN NEW.item_tipo_id IS NOT NULL
BEGIN
    UPDATE item_tipo
    SET qntd_disponivel = CASE NEW.tipo
        WHEN 'danificado' THEN qntd_disponivel - NEW.quantidade
        WHEN 'perdido' THEN qntd_disponivel - NEW.quantidade
        WHEN 'furto' THEN qntd_disponivel - NEW.quantidade
        WHEN 'encontrado' THEN MIN(qntd_total, qntd_disponivel + NEW.quantidade)
        ELSE qntd_disponivel
    END,
    atualizado_em = NEW.data
    WHERE id = NEW.item_tipo_id;
END;

-- Encontro (parcial ou total) de itens por quantidade resolve perdas abertas
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
        END,
        resolvida_em = CASE
            WHEN quantidade_resolvida + NEW.quantidade >= quantidade THEN NEW.data
            ELSE resolvida_em
        END
    WHERE item_tipo_id = NEW.item_tipo_id
      AND tipo IN ('perdido','furto')
      AND status_resolucao <> 'resolvida'
      AND id <> NEW.id;
END;
