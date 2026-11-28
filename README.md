# Sistema de Inventário e Gestão Maker — DEX0199

Sistema embarcado distribuído para controle de inventário, empréstimos (`BANCADA` e `CASA`), gestão de aulas (experiências pedagógicas), ocorrências, conferência de estoque e coleta de feedback em laboratórios Maker.

## Arquitetura do MVP

Em vez de guardar dados apenas na RAM da placa, o MVP integra **as duas ESP32** a um **servidor local Python + SQLite** rodando em qualquer computador (ou Raspberry Pi) na mesma rede Wi-Fi, acompanhado de um **painel web administrativo**.

```
┌─────────────────────────────┐         Wi-Fi / HTTP JSON         ┌──────────────────────────────────┐
│  Estação Óptica (ESP32-S3)  │ ─── POST /api/camera/leitura ───► │    Servidor Local (Python 3)     │
│  Câmera OV2640 + quirc QR   │                                   │    server/dex_server.py :8000    │
└─────────────────────────────┘                                   │                                  │
                                                                  │  • Banco SQLite (database/schema)│
┌─────────────────────────────┐      Wi-Fi / HTTP JSON (API)      │  • Triggers de integridade       │
│  Terminal Kiosk (ESP32 CYD) │ ◄───────────────────────────────► │  • Painel Web (http://PC:8000/)  │
│  Touch 2.8" + NFC PN532     │    login, emprestimo, aula,       └──────────────────────────────────┘
│  (+ RTC DS3231 opcional)    │    ocorrencia, conferencia, QR
└─────────────────────────────┘
```

### Por que essa arquitetura?
- **Persistência real e íntegra:** todos os cadastros, empréstimos, aulas, ocorrências e feedbacks ficam salvos no banco SQLite com triggers de validação (`database/schema/`).
- **Zero dependências no servidor:** o servidor usa apenas a biblioteca padrão do Python 3 (`sqlite3`, `http.server`). Não precisa instalar `pip` nem configurar servidor externo.
- **Integração desacoplada entre as ESP32:** a câmera ESP32-S3 publica os QR Codes lidos na fila do servidor, e o Terminal CYD consome automaticamente na tela em que o usuário está. Você pode inclusive testar o CYD **sem a câmera** usando o simulador de QR no painel web.
- **Gestão prática:** cadastrar novos crachás NFC, tipos de itens, resolver ocorrências e ver histórico/alertas fica muito mais fácil pelo painel web no navegador.

---

## Como Colocar Tudo para Funcionar (Passo a Passo)

### 1. Subir o Servidor Local e o Banco SQLite
Na raiz do repositório, execute:

```bash
python server/dex_server.py
```

Ao iniciar, o servidor:
- Cria automaticamente o banco SQLite a partir de `database/schema/*.sql` e carrega dados de demonstração (`database/seeds/demo.sql`), incluindo os dois crachás NFC já usados nos testes (`4D:87:4E:07` como Professor e `C0:3E:35:5C` como Monitor) e 5 itens de exemplo (`DEX-0001` a `DEX-0005`);
- Imprime no terminal o **IP local** (ex.: `192.168.1.100`), a porta (`8000`) e a `API_KEY`;
- Disponibiliza o painel web em `http://localhost:8000/` (usuário `admin`, senha `admin` — configurável em [server/config.json](server/config.json)).

> **Dica Windows:** na primeira execução, permita o acesso do Python no Firewall do Windows para redes privadas, para que as ESP32 consigam alcançar a porta `8000`.

### 2. Gravar o Terminal Kiosk (`firmware-cyd/`)
1. Edite [firmware-cyd/config.h](firmware-cyd/config.h) com seu `WIFI_SSID`, `WIFI_PASS` e o `SERVER_HOST` impresso pelo servidor.
2. Copie [firmware-cyd/User_Setup.h](firmware-cyd/User_Setup.h) para dentro da pasta da biblioteca `TFT_eSPI`.
3. Instale via Gerenciador de Bibliotecas da Arduino IDE: `TFT_eSPI`, `XPT2046_Touchscreen`, `Adafruit PN532`, `Adafruit BusIO`, `RTClib`, `ArduinoJson`.
4. Selecione a placa **ESP32 Dev Module** e faça o upload de [firmware-cyd/firmware-cyd.ino](firmware-cyd/firmware-cyd.ino).

Mais detalhes de pinagem e calibração em [firmware-cyd/README.md](firmware-cyd/README.md).

### 3. Gravar a Estação Óptica (`firmware-s3/`)
1. Edite [firmware-s3/config.h](firmware-s3/config.h) com seu `WIFI_SSID`, `WIFI_PASS`, `SERVER_HOST` e selecione o modelo da sua placa ESP32-S3 com câmera.
2. Instale apenas `ArduinoJson` (o decodificador de QR Code `quirc` já está embutido em `firmware-s3/src/quirc/`).
3. Selecione **ESP32S3 Dev Module** (com **PSRAM: OPI PSRAM** se sua placa tiver PSRAM) e faça o upload de [firmware-s3/firmware-s3.ino](firmware-s3/firmware-s3.ino).
4. Acesse `http://<IP_DA_S3>/` no navegador para ver a imagem da câmera e ajustar o foco.

Mais detalhes em [firmware-s3/README.md](firmware-s3/README.md).

### 4. Testar o Fluxo Completo
1. Abra o painel web (`http://localhost:8000/`) e veja `cyd-01` e `s3-01` ficarem **online** em **Visão Geral**.
2. Aproxime um crachá NFC no leitor PN532 do CYD (se for um crachá novo, o UID aparecerá na tela do CYD e em *Últimas Leituras* no painel — basta cadastrá-lo em **Usuários**).
3. No menu do CYD:
   - Toque em **AULA → INICIAR AULA** (como professor);
   - Toque em **EMPRESTIMO**, escolha `BANCADA` ou `CASA` e aponte um QR Code (ex.: `DEX-0001`) para a câmera ESP32-S3 ou aproxime uma tag NFC;
   - Para devolver, basta ler o mesmo item novamente;
   - Teste também **CADASTRAR**, **INVENTARIO**, **OCORRENCIA**, **CONFERIR** e encerramento de aula com **FEEDBACK (1 a 5)**.

---

## Estrutura do Repositório

| Pasta / Arquivo | Descrição |
| :--- | :--- |
| [server/](server/) | Servidor local Python (stdlib), API REST, painel web e testes automatizados (`test_server.py`). |
| [database/schema/](database/schema/) | Esquema SQLite modular (tabelas, triggers, índices, views e dados iniciais). |
| [database/seeds/](database/seeds/) | Dados de demonstração (`demo.sql`). |
| [firmware-cyd/](firmware-cyd/) | Firmware do Terminal Kiosk (ESP32-2432S028 / Cheap Yellow Display). |
| [firmware-s3/](firmware-s3/) | Firmware da Estação Óptica (ESP32-S3 + câmera + `quirc` embutido). |
| [docs/](docs/) | Documentação de hardware, banco de dados, aplicação e casos de uso. |

## Licença

Distribuído sob a licença MIT. Consulte [LICENSE](LICENSE).
