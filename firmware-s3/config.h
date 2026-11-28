#pragma once

// =====================================================================
// Configuracao da Estacao Optica (ESP32-S3 com Camera)
// Ajuste os valores abaixo antes de gravar na placa.
// =====================================================================

// Rede Wi-Fi (a mesma rede onde esta rodando o servidor Python)
#define WIFI_SSID   "SEU_WIFI_AQUI"
#define WIFI_PASS   "SUA_SENHA_AQUI"

// Endereco do PC/servidor rodando `python server/dex_server.py`
#define SERVER_HOST "192.168.1.100"
#define SERVER_PORT 8000
#define API_KEY     "dex0199-chave-local"

// Identificador desta camera no painel web
#define DEVICE_ID   "s3-01"
#define FW_VERSION  "1.0.0"

// =====================================================================
// Modelo da placa ESP32-S3 com camera (deixe APENAS UM descomentado)
// =====================================================================
#define CAMERA_MODEL_ESP32S3_EYE        // Freenove ESP32-S3-WROOM CAM / ESP32-S3-EYE / clones N16R8
// #define CAMERA_MODEL_XIAO_ESP32S3    // Seeed Studio XIAO ESP32S3 Sense
// #define CAMERA_MODEL_ESP32S3_CAM_LCD // ESP32-S3-CAM-LCD

// LED de feedback visual ao ler um QR Code (-1 desativa)
#define STATUS_LED_PIN     2
#define STATUS_LED_ACTIVE  HIGH

// Tempo minimo (ms) para reenviar o mesmo QR Code consecutivo
#define QR_COOLDOWN_MS     2500
#define HEARTBEAT_MS       15000
#define HTTP_TIMEOUT_MS    4000
