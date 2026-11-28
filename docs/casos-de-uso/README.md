# Casos de Uso Cobertos no MVP

| Caso de Uso | Onde Executar | Regra Principal |
| :--- | :--- | :--- |
| Autenticação por crachá NFC | Kiosk (CYD) | Sessão com TTL deslizante; crachás inativos/desconhecidos são bloqueados e auditados. |
| Iniciar / Encerrar Aula (Experiência) | Kiosk (CYD) | Apenas docente/admin; encerramento exige decisão sobre pendências e feedback (1 a 5). |
| Autorizar Monitor | Kiosk (CYD) | Professor aproxima o crachá do monitor para liberar empréstimos `CASA` por `ttl_autorizacao_horas`. |
| Empréstimo / Devolução Individual | Kiosk + Câmera S3 | Leitura NFC ou QR alterna automaticamente entre emprestar e devolver. Monitor sem autorização em `BANCADA` gera alerta automático na auditoria. |
| Empréstimo / Devolução por Quantidade | Kiosk + Câmera S3 | Ao ler a etiqueta da caixa, o Kiosk abre o seletor de quantidade e atualiza o estoque via trigger. |
| Cadastro de Itens e Usuários | Kiosk + Painel Web | Itens individuais podem ser cadastrados direto no Kiosk (por tipo) ou pelo Painel Web. |
| Registro e Resolução de Ocorrências | Kiosk + Painel Web | Kiosk registra `danificado`, `perdido`, `encontrado` ou `furto`; Painel Web retorna ao estoque ou dá baixa. |
| Conferência de Inventário | Kiosk + Painel Web | Kiosk lê itens presentes; ao encerrar, faltantes são registrados e listados no Painel Web. |
