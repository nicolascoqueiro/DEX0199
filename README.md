# Sistema de Inventario e Gestao Maker - ESP32 - DEX0199

Sistema embarcado distribuido para controle de inventário, empréstimos (bancada e armário), registro de ocorrências e coleta de feedback em laboratórios Maker.

## Hardware

- **Terminal Principal (Kiosk):** ESP32-2432S028 (Cheap Yellow Display) com tela touchscreen, leitor NFC V3 Red (PN532) e RTC DS3231SN via barramento I2C.
- **Estacao Optica:** ESP32-S3 com camera dedicada a leitura de QR Codes.

## Documentacao

- [Hardware e Pinagem](docs/hardware/)
- [Casos de Uso e Requisitos](docs/casos-de-uso/)
- [Arquitetura da Aplicacao](docs/arquitetura/)
- [Banco de Dados](docs/banco-de-dados/)
- [Diagramas UML](docs/uml/)

## Roadmap

- **Fase 1 (MVP):** Cadastro, listagem e remoção local de itens do inventário via RFID e tela touchscreen.
- **Fase 2:** Autenticacao com TTL, sincronizacao com servidor central, empréstimos, experiências pedagogicas e pesquisa de feedback.

## Licenca

Distribuido sob a licenca GNU General Public License v3.0. Consulte o arquivo `LICENSE` para mais informacoes.
