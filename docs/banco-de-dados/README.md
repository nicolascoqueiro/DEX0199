# Banco de Dados (SQLite)

O banco de dados do DEX0199 foi organizado em scripts modulares e ordenados em [database/schema/](../../database/schema/), aplicados automaticamente pelo servidor Python na primeira execução.

## Ordem de Carga (`database/schema/`)
- `01_config.sql` — configurações chave-valor e tabela `escola`.
- `02_dominio.sql` — `item_tipo` (individual ou por quantidade), `item_fisico`, `usuario` e `permissao`.
- `03_experiencia.sql` — `experiencia` (aulas/atividades) e `experiencia_docente`.
- `04_sessao_auth.sql` — `sessao` (TTL deslizante com hash SHA-256) e `autorizacao_sessao` (autorização de monitores).
- `05_inventario.sql` — `inventario_sessao` (sessões de conferência).
- `06_ocorrencias.sql` — `ocorrencia` (danificado, perdido, encontrado, furto, outro).
- `07_pesquisa_feedback.sql` — `pesquisa`, `pesquisa_opcao` e `feedback`.
- `08_registro.sql` — `registro` (log unificado e imutável de todos os eventos).
- `09_emprestimo_aberto.sql` — `emprestimo_aberto` (modalidades `bancada` e `casa` com prazo).
- `10_movimentacao_quantidade.sql` — movimentações de itens controlados por quantidade.
- `11_auditoria_sync.sql` — `auditoria` (incluindo alertas), `sync_estado` e `sync_fila`.
- `12_dispositivos.sql` — `dispositivo` (heartbeats das ESP32) e `leitura` (fila câmera → kiosk).
- `20_trg_*.sql` a `25_trg_*.sql` — triggers de integridade (disponibilidade, contador de aula, alerta de monitor sem autorização, validação de encerramento com feedback obrigatório, estoque por quantidade, ocorrências e sanidade temporal).
- `30_indices.sql` e `40_views.sql` — índices e views (`v_inventario_conferencia`, `v_historico`, `v_pendencias_experiencia`, `v_emprestimos_abertos`).
- `90_dados_iniciais.sql` — escola padrão, configurações, usuário técnico do painel e pesquisa de humor padrão.

## Diagramas Originais de Referência
Os diagramas originais de modelagem foram preservados em [img/](img/):
- [esquema_geral_tabelas.png](img/esquema_geral_tabelas.png)
- [esquema_db.png](img/esquema_db.png)
- [diagrama_de_estados.png](img/diagrama_de_estados.png)
- [fluxo_itens.png](img/fluxo_itens.png)
