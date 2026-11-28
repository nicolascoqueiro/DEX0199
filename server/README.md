# Servidor Local e Painel Web (DEX0199)

Servidor HTTP + banco SQLite local que integra o Terminal Kiosk (`ESP32 CYD`), a Estação Óptica (`ESP32-S3`) e o painel web de administração.

**Sem dependências externas:** roda com qualquer instalação padrão do **Python 3.8+**.

## Como Executar

```bash
# Iniciar normalmente (cria o banco na primeira execução com dados de demonstração)
python server/dex_server.py

# Recriar o banco do zero (apaga dados anteriores)
python server/dex_server.py --reset

# Criar banco limpo sem dados de demonstração
python server/dex_server.py --reset --sem-demo

# Especificar porta ou caminho do arquivo SQLite
python server/dex_server.py --porta 8000 --db ./meu_lab.db
```

### Onde o arquivo `.db` é salvo?
No Windows, por padrão o banco é salvo em `%LOCALAPPDATA%\DEX0199\dex0199.db` — fora da pasta do OneDrive — para evitar que a sincronização em nuvem corrompa o SQLite enquanto o servidor estiver aberto. Em Linux/macOS, fica em `server/dados/dex0199.db`. Você pode baixar uma cópia consistente a qualquer momento clicando em **Baixar Backup (.db)** no painel web.

## Configuração (`server/config.json`)

| Chave | Padrão | Descrição |
| :--- | :--- | :--- |
| `host` | `0.0.0.0` | Interface de rede (`0.0.0.0` aceita conexões das ESP32 na rede local). |
| `porta` | `8000` | Porta HTTP. |
| `api_key` | `dex0199-chave-local` | Chave enviada pelas ESP32 no cabeçalho `X-Api-Key`. |
| `admin_usuario` | `admin` | Usuário do painel web (HTTP Basic). |
| `admin_senha` | `admin` | Senha do painel web. |
| `db` | `""` | Caminho opcional do SQLite (vazio = local padrão). |

## Testes Automatizados

```bash
python server/test_server.py
```

A suíte sobe um servidor real em porta temporária com banco SQLite novo e testa autenticação, fila de leituras da câmera, empréstimo/devolução, aulas com feedback obrigatório, autorização de monitores com alerta automático de auditoria, estoque por quantidade, ocorrências e conferência de inventário.

## Principais Rotas da API

### Dispositivos (cabeçalho `X-Api-Key`)
- `GET /api/ping` — verifica status e retorna `epoch` + fuso horário para sincronizar o RTC.
- `POST /api/dispositivos/heartbeat` — registra dispositivo (`kiosk` ou `camera`) online no painel.
- `POST /api/camera/leitura` — usado pela `ESP32-S3` para enviar cada QR Code lido.
- `POST /api/kiosk/login` — valida UID NFC do crachá e devolve `token` de sessão + TTL.
- `GET /api/kiosk/leitura` — consome a leitura mais recente enviada pela câmera.

### Operações do Kiosk (`X-Api-Key` + `X-Sessao`)
- `GET /api/kiosk/itens`, `GET /api/kiosk/tipos`, `GET /api/kiosk/consulta?codigo=...`
- `POST /api/kiosk/cadastrar`, `POST /api/kiosk/movimentar`, `POST /api/kiosk/ocorrencia`
- `GET /api/kiosk/aula`, `POST /api/kiosk/aula/iniciar`, `POST /api/kiosk/aula/autorizar`, `POST /api/kiosk/aula/encerrar`
- `GET /api/kiosk/conferencia`, `POST /api/kiosk/conferencia/iniciar`, `POST /api/kiosk/conferencia/ler`, `POST /api/kiosk/conferencia/encerrar`
- `POST /api/kiosk/logout`
