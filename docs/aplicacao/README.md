# Arquitetura da Aplicação

O MVP adota uma arquitetura em **3 camadas na rede local**:

1. **Camada de Coleta e Interface Física (ESP32):**
   - **Terminal Kiosk (`firmware-cyd`):** autentica operadores por crachá NFC e executa fluxos de empréstimo, aula, cadastro, ocorrência e conferência via tela touchscreen.
   - **Estação Óptica (`firmware-s3`):** lê QR Codes continuamente e publica na fila `/api/camera/leitura`.

2. **Camada de Serviço e Persistência (`server/` + `database/`):**
   - `server/dex_server.py`: servidor HTTP multithread (stdlib Python) com autenticação `X-Api-Key` + `X-Sessao` para dispositivos e HTTP Basic para o painel web.
   - `server/servicos.py`: regras de negócio transacionais.
   - `server/db.py`: inicialização automática do SQLite em modo WAL com `PRAGMA foreign_keys = ON`.

3. **Camada de Gestão Web (`server/static/`):**
   - Painel responsivo para cadastro de usuários/crachás, tipos de itens, itens individuais, acompanhamento de empréstimos, resolução de ocorrências, conferências, auditoria/alertas, backup do `.db` e simulador de leitura QR.
