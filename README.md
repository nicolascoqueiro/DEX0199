# Sistema de Inventário e Gestão Maker - ESP32 - DEX0199

Sistema embarcado distribuído para controle de inventário, empréstimos (bancada e armário), registro de ocorrências e coleta de feedback em laboratórios Maker.

## Hardware

- **Terminal Principal (Kiosk):** ESP32-2432S028 (Cheap Yellow Display) com tela touchscreen, leitor NFC V3 Red (PN532) e RTC DS3231SN via barramento I2C.
- **Estação Óptica:** ESP32-S3 com câmera dedicada a leitura de QR Codes.

## Documentação

- [Hardware e Pinagem](docs/hardware/)
- [Casos de Uso e Requisitos](docs/casos-de-uso/)
- [Arquitetura da Aplicacao](docs/arquitetura/)
- [Banco de Dados](docs/banco-de-dados/)
- [Diagramas UML](docs/uml/)

## Roadmap

- **Fase 1 (MVP):** Cadastro, listagem e remoção local de itens do inventário via RFID e tela touchscreen.
- **Fase 2:** Autenticação com TTL, sincronização com servidor central, empréstimos, experiências pedagógicas e pesquisa de feedback.

## Licença

Distribuído sob a licença MIT License. Consulte o arquivo `LICENSE` para mais informações.
