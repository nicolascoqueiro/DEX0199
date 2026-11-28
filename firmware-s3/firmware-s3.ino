/*
 * DEX0199 - Firmware da Estacao Optica (ESP32-S3 com Camera)
 *
 * Responsavel por:
 *  - Capturar frames em escala de cinza (QVGA 320x240) via esp_camera;
 *  - Decodificar QR Codes localmente usando a biblioteca embarcada quirc
 *    (incluida em src/quirc/, sem depender de bibliotecas externas);
 *  - Enviar cada codigo lido para o servidor local Python/SQLite:
 *      POST http://<SERVER_HOST>:<SERVER_PORT>/api/camera/leitura
 *  - Enviar heartbeat periodico para o painel web (/api/dispositivos/heartbeat);
 *  - Disponibilizar pagina de diagnostico em http://<IP_DA_S3>/ com preview
 *    instantaneo (/capture) para facilitar o alinhamento e foco da lente.
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <WebServer.h>
#include <ArduinoJson.h>
#include "esp_camera.h"
#include "img_converters.h"

extern "C" {
#include "src/quirc/quirc.h"
}

#include "config.h"
#include "camera_pins.h"

WebServer web(80);

// Estruturas do quirc alocadas estaticamente (evita stack overflow na task)
static struct quirc* qr = nullptr;
static struct quirc_code qCode;
static struct quirc_data qData;

// Mutex para proteger acesso a camera entre a task de QR e o /capture HTTP
static SemaphoreHandle_t camMutex = nullptr;

// Estado compartilhado
static bool cameraOK = false;
static String ultimoQR = "";
static unsigned long ultimoQREm = 0;
static unsigned long totalLidos = 0;
static unsigned long ultimoEnvioStatus = 0;
static unsigned long ultimoHeartbeat = 0;

// =====================================================================
// FEEDBACK VISUAL
// =====================================================================
void piscarLed(int vezes = 2, int ms = 80) {
#if STATUS_LED_PIN >= 0
  for (int i = 0; i < vezes; i++) {
    digitalWrite(STATUS_LED_PIN, STATUS_LED_ACTIVE);
    delay(ms);
    digitalWrite(STATUS_LED_PIN, !STATUS_LED_ACTIVE);
    if (i + 1 < vezes) delay(ms);
  }
#endif
}

// =====================================================================
// COMUNICACAO COM O SERVIDOR LOCAL PYTHON
// =====================================================================
bool enviarLeituraServidor(const String& codigo) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[HTTP] Wi-Fi desconectado, leitura nao enviada.");
    return false;
  }

  HTTPClient http;
  String url = String("http://") + SERVER_HOST + ":" + String(SERVER_PORT) + "/api/camera/leitura";
  http.setTimeout(HTTP_TIMEOUT_MS);
  if (!http.begin(url)) return false;

  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Api-Key", API_KEY);
  http.addHeader("X-Dispositivo", DEVICE_ID);

  JsonDocument payload;
  payload["dispositivo"] = DEVICE_ID;
  payload["codigo"] = codigo;
  payload["origem"] = "qr";
  String body;
  serializeJson(payload, body);

  int httpCode = http.POST(body);
  String resp = (httpCode > 0) ? http.getString() : "";
  http.end();

  ultimoEnvioStatus = (httpCode > 0) ? (unsigned long)httpCode : 0;
  if (httpCode == 200) {
    Serial.println("[SRV] Leitura aceita: " + codigo);
    return true;
  }
  Serial.printf("[SRV] Falha HTTP %d: %s\n", httpCode, resp.c_str());
  return false;
}

void enviarHeartbeat() {
  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;
  String url = String("http://") + SERVER_HOST + ":" + String(SERVER_PORT) + "/api/dispositivos/heartbeat";
  http.setTimeout(HTTP_TIMEOUT_MS);
  if (!http.begin(url)) return;

  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Api-Key", API_KEY);
  http.addHeader("X-Dispositivo", DEVICE_ID);

  JsonDocument payload;
  payload["id"] = DEVICE_ID;
  payload["tipo"] = "camera";
  payload["ip"] = WiFi.localIP().toString();
  payload["firmware"] = FW_VERSION;
  JsonObject info = payload["info"].to<JsonObject>();
  info["rssi"] = WiFi.RSSI();
  info["camera"] = cameraOK;
  info["lidos"] = totalLidos;
  String body;
  serializeJson(payload, body);

  http.POST(body);
  http.end();
}

// =====================================================================
// CAMERA + QUIRC
// =====================================================================
bool iniciarCamera() {
  camera_config_t cfg = {};
  cfg.ledc_channel = LEDC_CHANNEL_0;
  cfg.ledc_timer   = LEDC_TIMER_0;
  cfg.pin_d0       = Y2_GPIO_NUM;
  cfg.pin_d1       = Y3_GPIO_NUM;
  cfg.pin_d2       = Y4_GPIO_NUM;
  cfg.pin_d3       = Y5_GPIO_NUM;
  cfg.pin_d4       = Y6_GPIO_NUM;
  cfg.pin_d5       = Y7_GPIO_NUM;
  cfg.pin_d6       = Y8_GPIO_NUM;
  cfg.pin_d7       = Y9_GPIO_NUM;
  cfg.pin_xclk     = XCLK_GPIO_NUM;
  cfg.pin_pclk     = PCLK_GPIO_NUM;
  cfg.pin_vsync    = VSYNC_GPIO_NUM;
  cfg.pin_href     = HREF_GPIO_NUM;
  cfg.pin_sccb_sda = SIOD_GPIO_NUM;
  cfg.pin_sccb_scl = SIOC_GPIO_NUM;
  cfg.pin_pwdn     = PWDN_GPIO_NUM;
  cfg.pin_reset    = RESET_GPIO_NUM;
  cfg.xclk_freq_hz = 20000000;
  cfg.pixel_format = PIXFORMAT_GRAYSCALE;
  cfg.frame_size   = FRAMESIZE_QVGA; // 320x240: rapido e nitido para QR
  cfg.fb_count     = 1;
  cfg.grab_mode    = CAMERA_GRAB_LATEST;
  cfg.fb_location  = psramFound() ? CAMERA_FB_IN_PSRAM : CAMERA_FB_IN_DRAM;

  esp_err_t err = esp_camera_init(&cfg);
  if (err != ESP_OK) {
    Serial.printf("[CAM] Erro ao inicializar camera: 0x%x\n", err);
    return false;
  }

  sensor_t* s = esp_camera_sensor_get();
  if (s != nullptr) {
    s->set_contrast(s, 1);
    s->set_brightness(s, 0);
    s->set_gain_ctrl(s, 1);
    s->set_exposure_ctrl(s, 1);
  }

  qr = quirc_new();
  if (!qr || quirc_resize(qr, 320, 240) < 0) {
    Serial.println("[QR] Falha ao alocar buffer quirc.");
    return false;
  }

  Serial.println("[CAM] Camera QVGA GRAYSCALE + quirc prontos!");
  return true;
}

void processarFrameQR() {
  if (!cameraOK || !qr) return;

  camera_fb_t* fb = nullptr;
  if (xSemaphoreTake(camMutex, pdMS_TO_TICKS(200)) == pdTRUE) {
    fb = esp_camera_fb_get();
    if (fb) {
      int w = 0, h = 0;
      uint8_t* buf = quirc_begin(qr, &w, &h);
      if (buf && (int)fb->width == w && (int)fb->height == h) {
        memcpy(buf, fb->buf, (size_t)w * (size_t)h);
        esp_camera_fb_return(fb);
        fb = nullptr;
        xSemaphoreGive(camMutex);

        quirc_end(qr);
        int count = quirc_count(qr);
        for (int i = 0; i < count; i++) {
          quirc_extract(qr, i, &qCode);
          if (quirc_decode(&qCode, &qData) == QUIRC_SUCCESS) {
            String codigo = String((const char*)qData.payload);
            codigo.trim();
            if (codigo.length() > 0) {
              unsigned long agora = millis();
              if (codigo != ultimoQR || (agora - ultimoQREm >= QR_COOLDOWN_MS)) {
                ultimoQR = codigo;
                ultimoQREm = agora;
                totalLidos++;
                Serial.println("[QR] Lido: " + codigo);
                if (enviarLeituraServidor(codigo)) {
                  piscarLed(2, 60);
                } else {
                  piscarLed(4, 40);
                }
              }
            }
          }
        }
        return;
      }
      esp_camera_fb_return(fb);
    }
    xSemaphoreGive(camMutex);
  }
}

void taskLeitorQR(void* pvParameters) {
  (void)pvParameters;
  for (;;) {
    processarFrameQR();
    vTaskDelay(pdMS_TO_TICKS(120));
  }
}

// =====================================================================
// PAGINA DE DIAGNOSTICO / PREVIEW (http://<IP_DA_S3>/)
// =====================================================================
void configurarWebDiagnostico() {
  web.on("/", HTTP_GET, []() {
    String html = F(
      "<!doctype html><html><head><meta charset='utf-8'>"
      "<title>DEX0199 Camera S3</title>"
      "<style>body{font-family:sans-serif;background:#0f172a;color:#f1f5f9;padding:20px;}"
      "img{border:2px solid #3b82f6;border-radius:8px;max-width:100%;}"
      ".box{background:#1e293b;padding:12px;border-radius:8px;margin:12px 0;max-width:420px;}</style>"
      "</head><body><h2>DEX0199 - Estacao Optica (ESP32-S3)</h2><div class='box'>"
    );
    html += "<b>Dispositivo:</b> " + String(DEVICE_ID) + "<br>";
    html += "<b>Servidor:</b> http://" + String(SERVER_HOST) + ":" + String(SERVER_PORT) + "<br>";
    html += "<b>Camera:</b> " + String(cameraOK ? "OK" : "ERRO") + "<br>";
    html += "<b>Total lidos:</b> " + String(totalLidos) + "<br>";
    html += "<b>Ultimo QR:</b> <code>" + (ultimoQR.length() ? ultimoQR : String("(nenhum)")) + "</code><br>";
    html += "<b>Ultimo HTTP:</b> " + String(ultimoEnvioStatus) + "</div>";
    html += "<img id='cam' src='/capture' width='320' height='240'><br>";
    html += "<p><button onclick=\"document.getElementById('cam').src='/capture?t='+Date.now()\">Atualizar foto</button></p>";
    html += "<script>setInterval(()=>{document.getElementById('cam').src='/capture?t='+Date.now();},1500);</script>";
    html += "</body></html>";
    web.send(200, "text/html", html);
  });

  web.on("/capture", HTTP_GET, []() {
    if (!cameraOK) {
      web.send(503, "text/plain", "Camera indisponivel");
      return;
    }
    if (xSemaphoreTake(camMutex, pdMS_TO_TICKS(500)) != pdTRUE) {
      web.send(503, "text/plain", "Camera ocupada");
      return;
    }
    camera_fb_t* fb = esp_camera_fb_get();
    if (!fb) {
      xSemaphoreGive(camMutex);
      web.send(500, "text/plain", "Falha ao capturar frame");
      return;
    }
    uint8_t* jpgBuf = nullptr;
    size_t jpgLen = 0;
    bool ok = frame2jpg(fb, 80, &jpgBuf, &jpgLen);
    esp_camera_fb_return(fb);
    xSemaphoreGive(camMutex);

    if (!ok || !jpgBuf) {
      web.send(500, "text/plain", "Falha ao converter JPEG");
      return;
    }
    web.setContentLength(jpgLen);
    web.send(200, "image/jpeg", "");
    WiFiClient client = web.client();
    client.write(jpgBuf, jpgLen);
    free(jpgBuf);
  });

  web.on("/api/status", HTTP_GET, []() {
    JsonDocument doc;
    doc["id"] = DEVICE_ID;
    doc["camera"] = cameraOK;
    doc["lidos"] = totalLidos;
    doc["ultimo_qr"] = ultimoQR;
    doc["http_status"] = ultimoEnvioStatus;
    String out;
    serializeJson(doc, out);
    web.send(200, "application/json", out);
  });

  web.begin();
}

// =====================================================================
// SETUP & LOOP
// =====================================================================
void setup() {
  Serial.begin(115200);
  delay(400);
  Serial.println("\n[DEX0199] Iniciando Estacao Optica (ESP32-S3)...");

#if STATUS_LED_PIN >= 0
  pinMode(STATUS_LED_PIN, OUTPUT);
  digitalWrite(STATUS_LED_PIN, !STATUS_LED_ACTIVE);
#endif

  camMutex = xSemaphoreCreateMutex();
  cameraOK = iniciarCamera();

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("[WiFi] Conectando");
  unsigned long t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 15000) {
    delay(300);
    Serial.print(".");
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("[WiFi] Conectado! IP S3: " + WiFi.localIP().toString());
    Serial.println("[WEB] Preview da camera em: http://" + WiFi.localIP().toString() + "/");
    enviarHeartbeat();
    configurarWebDiagnostico();
    piscarLed(1, 150);
  } else {
    Serial.println("[WiFi] Nao conectou no boot; tentara reconectar.");
  }

  // Task dedicada no core 1 com 24KB de stack para decodificacao QR
  if (cameraOK) {
    xTaskCreatePinnedToCore(taskLeitorQR, "qr_task", 24576, nullptr, 1, nullptr, 1);
  }
}

void loop() {
  if (WiFi.status() == WL_CONNECTED) {
    web.handleClient();
  }

  if (millis() - ultimoHeartbeat >= HEARTBEAT_MS) {
    ultimoHeartbeat = millis();
    if (WiFi.status() == WL_CONNECTED) {
      enviarHeartbeat();
    } else {
      WiFi.reconnect();
    }
  }
  delay(10);
}
