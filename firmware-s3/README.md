# Firmware Estação Óptica (`ESP32-S3` com Câmera)

Firmware responsável pela leitura contínua de **QR Codes** na estação óptica `ESP32-S3` e envio automático dos códigos lidos para o servidor local do **DEX0199**, que os repassa instantaneamente ao Terminal Kiosk (`CYD`).

## Características
- **Decodificador `quirc` embutido** em `src/quirc/`: não precisa instalar nenhuma biblioteca externa de QR Code (evita incompatibilidades com versões novas do core ESP32).
- **Captura em escala de cinza QVGA (320×240)** em tarefa FreeRTOS dedicada no Core 1.
- **Debouncing inteligente (`QR_COOLDOWN_MS`):** evita leituras duplicadas enquanto a etiqueta permanece na frente da lente.
- **Página web de diagnóstico e foco:** acesse `http://<IP_DA_S3>/` no navegador para ver a captura da câmera em tempo real e o último QR lido — ideal para calibrar a distância e o foco da lente durante a montagem física.

## Bibliotecas Necessárias (Arduino IDE)

Instale apenas:
- `ArduinoJson` (v7 — Benoit Blanchon)

(`esp_camera.h`, `WiFi.h`, `HTTPClient.h` e `WebServer.h` já fazem parte do pacote oficial **esp32 by Espressif Systems**.)

## Configuração Antes do Upload

Edite [config.h](config.h):
1. Configure `WIFI_SSID`, `WIFI_PASS`, `SERVER_HOST` (IP do PC rodando o servidor Python) e `API_KEY`.
2. Deixe descomentado apenas o modelo correspondente à sua placa `ESP32-S3`:
   - `CAMERA_MODEL_ESP32S3_EYE` (padrão — compatível com Freenove ESP32-S3-WROOM CAM, ESP32-S3-EYE e módulos N16R8-CAM);
   - `CAMERA_MODEL_XIAO_ESP32S3` (Seeed Studio XIAO ESP32S3 Sense);
   - `CAMERA_MODEL_ESP32S3_CAM_LCD`.

As pinagens completas estão em [camera_pins.h](camera_pins.h).

## Configurações Recomendadas na Arduino IDE
- **Board:** `ESP32S3 Dev Module`
- **PSRAM:** `OPI PSRAM` (se sua placa possuir PSRAM de 8MB, como N16R8; caso não possua, `Disabled` também funciona)
- **USB CDC On Boot:** `Enabled` (para ver os logs no Monitor Serial pela porta USB nativa)
- **Partition Scheme:** `Huge APP (3MB No OTA/1MB SPIFFS)` (recomendado; também cabe em `Default 4MB`)

## Integração com o Servidor
- A cada QR Code decodificado, envia `POST http://<SERVER_HOST>:8000/api/camera/leitura` com `{"dispositivo":"s3-01","codigo":"...","origem":"qr"}`.
- A cada 15 segundos, envia `POST /api/dispositivos/heartbeat` para aparecer como **online** no painel web.
