#pragma once

// =====================================================================
// Configuracao do Terminal Kiosk (ESP32-2432S028 / CYD)
// Ajuste os valores abaixo antes de gravar na placa.
// =====================================================================

// Rede Wi-Fi (a mesma rede onde esta rodando o servidor Python)
#define WIFI_SSID   "SEU_WIFI_AQUI"
#define WIFI_PASS   "SUA_SENHA_AQUI"

// Endereco do PC/servidor rodando `python server/dex_server.py`
// (o proprio servidor imprime o IP correto ao iniciar)
#define SERVER_HOST "192.168.1.100"
#define SERVER_PORT 8000
#define API_KEY     "dex0199-chave-local"

// Identificador deste terminal no painel web
#define DEVICE_ID   "cyd-01"
#define FW_VERSION  "1.0.0"

// Calibracao do touchscreen resistivo XPT2046 (padrao CYD em paisagem)
#define TOUCH_MIN_X 200
#define TOUCH_MAX_X 3700
#define TOUCH_MIN_Y 240
#define TOUCH_MAX_Y 3800

// Intervalos (ms)
#define POLL_QR_MS         700
#define HEARTBEAT_MS       15000
#define HTTP_TIMEOUT_MS    4500
#define NFC_COOLDOWN_MS    1200
