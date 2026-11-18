# Firmware Terminal Kiosk (ESP32-2432S028 / CYD)

Firmware responsável pela interface humano-computador (IHC), leitura de tags RFID/NFC e controle de acesso local no terminal **ESP32-2432S028 (Cheap Yellow Display)**, desenvolvido na Arduino IDE.

## Ambiente de Desenvolvimento e Bibliotecas

O código foi estruturado na **Arduino IDE** utilizando as seguintes bibliotecas:

* `TFT_eSPI`: Controle do display TFT LCD 2.8" (driver ILI9341).
* `Adafruit_PN532`: Comunicação e leitura de tags padrão ISO14443A com o módulo NFC.
* `Adafruit_BusIO`: Dependência para abstração dos barramentos I2C e SPI.
* `Wire`: Gerenciamento do barramento I2C secundário dedicado (`TwoWire(1)`).

## Configuração de Hardware e Pinagem

### Display (CYD)
* **Backlight (`TFT_BL`):** `GPIO 21`
* **Orientação:** Modo paisagem (`setRotation(1)` — 320x240 pixels)

### Módulo NFC (Elechouse PN532 V3 Red)
O leitor opera em protocolo **I2C** (chaves DIP da placa configuradas em `1` e `0` conforme serigrafia) conectado ao conector `CN1` da placa CYD. Foi instanciado um barramento I2C secundário (`TwoWire(1)`) para evitar conflitos com os pinos SPI nativos do display:

| Pino CYD (`CN1`) | Pino PN532 V3 | Função |
| :--- | :--- | :--- |
| `3V3` | `VCC` | Alimentação 3.3V |
| `GND` | `GND` | Referência Terra |
| `IO27` | `SDA` | Linha de Dados I2C (`NFC_SDA`) |
| `IO22` | `SCL` | Linha de Clock I2C (`NFC_SCL`) |

## Funcionamento Implementado

1. **Inicialização:** Ativa o backlight do display, inicializa a interface gráfica e consulta a versão de firmware do chip PN532 a 100 kHz.
2. **Leitura Contínua:** Executa polling passivo para tags `PN532_MIFARE_ISO14443A` com timeout de 500 ms.
3. **Validação de Acesso:** Formata o UID lido em hexadecimal e verifica a autorização local, exibindo o retorno visual (`ACESSO PERMITIDO` ou `ACESSO NEGADO`) na tela e retornando à tela inicial após 4 segundos.

## Próximos Passos (Integração MVP)

* Ativação e calibração do controlador touchscreen (`XPT2046`) para navegação nos menus.
* Implementação de sessão autenticada com *Time-To-Live* (TTL).
* Integração com o banco de dados SQLite local (substituindo a lista estática de UIDs).
* Compartilhamento do barramento I2C com o módulo RTC `DS3231SN`.
