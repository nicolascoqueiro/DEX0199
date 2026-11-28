# Firmware Terminal Kiosk (`ESP32-2432S028` / CYD)

Firmware responsável pela interface touchscreen, leitura de crachás e tags NFC (`PN532`), relógio opcional (`DS3231`) e comunicação via Wi-Fi (HTTP JSON) com o servidor local Python/SQLite do **DEX0199**.

## Bibliotecas Necessárias (Arduino IDE)

Instale pelo **Gerenciador de Bibliotecas**:
- `TFT_eSPI` (Bodmer)
- `XPT2046_Touchscreen` (Paul Stoffregen)
- `Adafruit PN532` + `Adafruit BusIO`
- `RTClib` (Adafruit)
- `ArduinoJson` (v7 — Benoit Blanchon)

> **Importante (`TFT_eSPI`):** substitua o arquivo `User_Setup.h` dentro da pasta da biblioteca (`Documents\Arduino\libraries\TFT_eSPI\User_Setup.h`) pelo arquivo [User_Setup.h](User_Setup.h) deste diretório.

## Configuração Antes do Upload

Edite [config.h](config.h):
```cpp
#define WIFI_SSID   "SUA_REDE"
#define WIFI_PASS   "SUA_SENHA"
#define SERVER_HOST "192.168.1.100" // IP exibido ao rodar `python server/dex_server.py`
#define SERVER_PORT 8000
#define API_KEY     "dex0199-chave-local"
```

Na Arduino IDE, selecione a placa **ESP32 Dev Module** e grave [firmware-cyd.ino](firmware-cyd.ino).

## Pinagem

### Touchscreen (`XPT2046` — SPI dedicado interno da CYD)
| Pino CYD | Função |
| :--- | :--- |
| `IO33` | `XPT2046_CS` |
| `IO36` | `XPT2046_IRQ` |
| `IO32` | `XPT2046_MOSI` |
| `IO39` | `XPT2046_MISO` |
| `IO25` | `XPT2046_CLK` |

### Barramento I2C Externo (Conector `CN1` — `PN532` + `DS3231` opcional)
Configure as chaves DIP do módulo **PN532 V3 Red** para modo **I2C** (`1` e `0`). O `DS3231` (endereço `0x68`) compartilha o mesmo barramento com o `PN532` (`0x24`) e é opcional: se não estiver conectado, o firmware inicia normalmente.

| Pino CYD (`CN1`) | PN532 V3 | DS3231 (Opcional) | Função |
| :--- | :--- | :--- | :--- |
| `3V3` | `VCC` | `VCC` | Alimentação 3.3V |
| `GND` | `GND` | `GND` | Terra |
| `IO27` | `SDA / TXD` | `SDA` | Dados I2C |
| `IO22` | `SCL / RXD` | `SCL` | Clock I2C |

## Telas e Fluxos no Terminal

1. **Login por Crachá NFC:** valida no servidor, exibe o perfil (`PROFESSOR`, `MONITOR` ou `ADMIN`) e renova o TTL a cada toque ou leitura. Crachás não cadastrados exibem o UID na tela para facilitar o cadastro no painel web.
2. **Empréstimo / Devolução:** modalidades `BANCADA` (vinculada à aula aberta) e `CASA` (com prazo). Lê tanto NFC quanto QR Codes enviados pela câmera ESP32-S3. Itens controlados por quantidade abrem o seletor numérico (`-5`, `-1`, `+1`, `+5`).
3. **Gestão de Aula:** professor inicia a aula, autoriza monitores aproximando o crachá do monitor e encerra a aula definindo o destino de pendências e respondendo à pesquisa de humor (`1` a `5`).
4. **Inventário & Consulta:** lista paginada de itens e estoque; aproximar uma tag/QR nesta tela consulta o estado atual do item.
5. **Cadastrar Item:** seleciona o tipo de item e lê a tag NFC ou QR Code para cadastrar direto no banco.
6. **Ocorrências:** registra `DANIFICADO`, `PERDIDO`, `ENCONTRADO` ou `FURTO` via NFC/QR.
7. **Conferência de Inventário:** inicia sessão de conferência, conta itens lidos vs. faltantes e encerra gerando relatório no painel web.
