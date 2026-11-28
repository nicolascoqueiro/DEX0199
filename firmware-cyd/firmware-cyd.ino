/*
 * DEX0199 - Firmware do Terminal Kiosk (ESP32-2432S028 / Cheap Yellow Display)
 *
 * Responsavel por:
 *  - Autenticacao por cracha NFC (PN532 via I2C dedicado CN1) com sessao TTL no servidor;
 *  - Interface touchscreen (XPT2046 + TFT_eSPI 320x240):
 *      * Emprestimo e Devolucao (Bancada / Casa + itens por quantidade);
 *      * Aulas / Experiencias (Iniciar, Autorizar Monitor via NFC, Encerrar com Feedback 1..5);
 *      * Inventario paginado + Consulta rapida por NFC/QR;
 *      * Cadastro de itens por tipo via NFC ou QR Code da ESP32-S3;
 *      * Registro de Ocorrencias (Danificado, Perdido, Encontrado, Furto);
 *      * Conferencia de Inventario;
 *  - Integracao com o servidor local Python/SQLite via HTTP JSON (Wi-Fi);
 *  - Consumo automatico de QR Codes lidos pela estacao optica ESP32-S3;
 *  - Suporte opcional ao RTC DS3231SN no mesmo barramento I2C (0x68).
 */

#include <Wire.h>
#include <SPI.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <TFT_eSPI.h>
#include <XPT2046_Touchscreen.h>
#include <Adafruit_PN532.h>
#include <RTClib.h>
#include <ArduinoJson.h>

#include "config.h"

// ===== PINOS HARDWARE CYD (ESP32-2432S028) =====
#define TFT_BL       21

// Touchscreen XPT2046 (SPI dedicado na CYD)
#define XPT2046_IRQ  36
#define XPT2046_MOSI 32
#define XPT2046_MISO 39
#define XPT2046_CLK  25
#define XPT2046_CS   33

// Barramento I2C dedicado no conector CN1 (PN532 0x24 + DS3231 opcional 0x68)
#define I2C_SDA      27
#define I2C_SCL      22

// ===== INSTANCIAS =====
TFT_eSPI tft = TFT_eSPI();
SPIClass touchSPI = SPIClass(VSPI);
XPT2046_Touchscreen ts(XPT2046_CS, XPT2046_IRQ);

TwoWire I2CExt = TwoWire(1);
Adafruit_PN532 nfc(-1, -1, &I2CExt);
RTC_DS3231 rtc;

// ===== CORES (RGB565) =====
#define COR_FUNDO    0x0861
#define COR_CARD     0x18E3
#define COR_AZUL     0x2D7F
#define COR_AZUL_ESC 0x192B
#define COR_BRANCO   0xFFFF
#define COR_VERDE    0x1D86
#define COR_VERDE_OK 0x07E0
#define COR_VERMELHO 0xC8A2
#define COR_AMARELO  0xFFE0
#define COR_LARANJA  0xD340
#define COR_ROXO     0x6194
#define COR_CINZA    0x7BEF
#define COR_CINZA_E  0x39E7

// ===== TELAS =====
enum Tela {
  TELA_LOGIN,
  TELA_MENU,
  TELA_EMPRESTIMO,
  TELA_QUANTIDADE,
  TELA_AULA,
  TELA_AULA_AUTORIZAR,
  TELA_AULA_DECISAO,
  TELA_AULA_FEEDBACK,
  TELA_INVENTARIO,
  TELA_CAD_TIPO,
  TELA_CAD_LER,
  TELA_OCORRENCIA,
  TELA_CONFERENCIA
};

Tela telaAtual = TELA_LOGIN;

// ===== HARDWARE / CONEXAO =====
bool nfcOK = false;
bool rtcOK = false;
bool servidorOK = false;
unsigned long ultimoHeartbeat = 0;
unsigned long ultimoPollQR = 0;
unsigned long ultimoToque = 0;
unsigned long ultimoNFC = 0;

// ===== SESSAO DO USUARIO =====
String sessaoToken = "";
String usuarioNome = "";
String usuarioPerfil = "";
bool podeGerenciarAula = false;
bool aulaAberta = false;
String aulaNome = "";
int aulaItensAbertos = 0;
bool monitorAutorizado = true;
String monitorAutorizador = "";
unsigned long inicioAtividade = 0;
unsigned long sessaoTtlMs = 300000; // atualizado pelo servidor no login

// ===== ESTADO DAS TELAS =====
String msgStatus = "";
bool msgErro = false;

// Emprestimo
String modoEmprestimo = "bancada"; // "bancada" ou "casa"
String qtdCodigo = "";
String qtdOrigem = "qr";
String qtdNome = "";
int qtdDisp = 0;
int qtdTotal = 0;
int qtdSel = 1;

// Aula encerramento
String aulaDecisao = "sem_pendencia";
int aulaPendencias = 0;

// Inventario paginado
struct ItemResumo {
  String nome;
  String estado;
  String detalhe;
};
ItemResumo invItens[5];
int invCount = 0;
int invPag = 0;
int invPaginas = 1;
int invTotal = 0;

// Cadastro (tipos paginados)
struct TipoResumo {
  int id;
  String nome;
};
TipoResumo tiposLista[4];
int tiposCount = 0;
int tiposPag = 0;
int tiposPaginas = 1;
int tipoSelecionadoId = 0;
String tipoSelecionadoNome = "";

// Ocorrencia
String tipoOcorrencia = "danificado";

// Conferencia
bool confAberta = false;
int confTotal = 0;
int confLidos = 0;
int confEmp = 0;
int confFaltando = 0;

// =====================================================================
// PROTOTIPOS
// =====================================================================
void desenharTelaLogin();
void desenharTelaMenu();
void desenharTelaEmprestimo();
void desenharTelaQuantidade();
void desenharTelaAula();
void desenharTelaAutorizar();
void desenharTelaDecisaoAula();
void desenharTelaFeedback();
void desenharTelaInventario();
void desenharTelaCadTipo();
void desenharTelaCadLer();
void desenharTelaOcorrencia();
void desenharTelaConferencia();

// =====================================================================
// UTILITARIOS DE TEXTO / INTERFACE
// =====================================================================
String cortar(const String& s, int maxLen) {
  if ((int)s.length() <= maxLen) return s;
  if (maxLen <= 2) return s.substring(0, maxLen);
  return s.substring(0, maxLen - 2) + "..";
}

void imprimirQuebrado(int x, int y, int maxChars, int maxLinhas, const String& texto, uint16_t cor, uint16_t fundo) {
  tft.setTextColor(cor, fundo);
  tft.setTextSize(1);
  int inicio = 0;
  int len = texto.length();
  for (int l = 0; l < maxLinhas && inicio < len; l++) {
    int fim = min(len, inicio + maxChars);
    if (fim < len) {
      int esp = texto.lastIndexOf(' ', fim);
      if (esp > inicio) fim = esp;
    }
    String linha = texto.substring(inicio, fim);
    linha.trim();
    tft.setCursor(x, y + l * 12);
    tft.print(linha);
    inicio = fim;
    while (inicio < len && texto[inicio] == ' ') inicio++;
  }
}

void desenharCabecalho(const char* titulo, bool comSair = false) {
  tft.fillRect(0, 0, 320, 32, COR_AZUL);
  tft.setTextColor(COR_BRANCO, COR_AZUL);
  tft.setTextSize(2);
  tft.setCursor(8, 8);
  tft.print(titulo);
  if (comSair) {
    tft.fillRoundRect(256, 4, 58, 24, 5, COR_VERMELHO);
    tft.drawRoundRect(256, 4, 58, 24, 5, COR_BRANCO);
    tft.setTextColor(COR_BRANCO, COR_VERMELHO);
    tft.setTextSize(1);
    tft.setCursor(273, 12);
    tft.print("SAIR");
  }
}

void desenharBotao(int x, int y, int w, int h, uint16_t cor, const char* texto, int textSize = 2) {
  tft.fillRoundRect(x, y, w, h, 7, cor);
  tft.drawRoundRect(x, y, w, h, 7, COR_BRANCO);
  tft.setTextColor(COR_BRANCO, cor);
  tft.setTextSize(textSize);
  int charW = 6 * textSize;
  int charH = 8 * textSize;
  int tx = x + (w - (int)strlen(texto) * charW) / 2;
  int ty = y + (h - charH) / 2;
  tft.setCursor(max(x + 4, tx), ty);
  tft.print(texto);
}

bool dentro(int x, int y, int bx, int by, int bw, int bh) {
  return x >= bx && x <= (bx + bw) && y >= by && y <= (by + bh);
}

void desenharBoxStatus(int y, int h) {
  uint16_t borda = msgStatus.length() == 0 ? COR_CINZA_E : (msgErro ? COR_VERMELHO : COR_VERDE_OK);
  uint16_t textoCor = msgErro ? COR_VERMELHO : COR_VERDE_OK;
  if (msgStatus.length() == 0) textoCor = COR_CINZA;
  tft.fillRoundRect(10, y, 300, h, 6, COR_CARD);
  tft.drawRoundRect(10, y, 300, h, 6, borda);
  if (msgStatus.length() > 0) {
    imprimirQuebrado(16, y + 6, 46, max(1, (h - 10) / 12), msgStatus, textoCor, COR_CARD);
  }
}

String formatarUID(uint8_t* uid, uint8_t len) {
  String out = "";
  for (uint8_t i = 0; i < len; i++) {
    if (uid[i] < 0x10) out += "0";
    out += String(uid[i], HEX);
    if (i < len - 1) out += ":";
  }
  out.toUpperCase();
  return out;
}

String urlEncode(const String& s) {
  String out = "";
  const char hex[] = "0123456789ABCDEF";
  for (size_t i = 0; i < s.length(); i++) {
    char c = s[i];
    if (isalnum((unsigned char)c) || c == '-' || c == '_' || c == '.' || c == ':') {
      out += c;
    } else {
      out += '%';
      out += hex[(c >> 4) & 0x0F];
      out += hex[c & 0x0F];
    }
  }
  return out;
}

// =====================================================================
// CLIENTE HTTP -> SERVIDOR LOCAL PYTHON
// =====================================================================
void encerrarSessaoLocal(const String& aviso = "") {
  sessaoToken = "";
  usuarioNome = "";
  usuarioPerfil = "";
  podeGerenciarAula = false;
  aulaAberta = false;
  aulaNome = "";
  msgStatus = aviso;
  msgErro = aviso.length() > 0;
  desenharTelaLogin();
}

int apiRequest(const char* metodo, const String& path, const String& corpoJson, JsonDocument& docOut, bool exigirSessao = true) {
  if (WiFi.status() != WL_CONNECTED) {
    servidorOK = false;
    docOut["msg"] = "Wi-Fi desconectado";
    return -1;
  }

  HTTPClient http;
  String url = String("http://") + SERVER_HOST + ":" + String(SERVER_PORT) + path;
  http.setTimeout(HTTP_TIMEOUT_MS);
  if (!http.begin(url)) {
    servidorOK = false;
    docOut["msg"] = "Falha ao abrir HTTP";
    return -1;
  }

  http.addHeader("X-Api-Key", API_KEY);
  http.addHeader("X-Dispositivo", DEVICE_ID);
  if (exigirSessao && sessaoToken.length() > 0) {
    http.addHeader("X-Sessao", sessaoToken);
  }
  if (corpoJson.length() > 0) {
    http.addHeader("Content-Type", "application/json");
  }

  int code = -1;
  if (strcmp(metodo, "GET") == 0) {
    code = http.GET();
  } else if (strcmp(metodo, "POST") == 0) {
    code = http.POST(corpoJson.length() > 0 ? corpoJson : "{}");
  }

  String resp = (code > 0) ? http.getString() : "";
  http.end();

  if (code <= 0) {
    servidorOK = false;
    docOut["msg"] = "Servidor offline (" + String(SERVER_HOST) + ")";
    return code;
  }

  servidorOK = true;
  if (resp.length() > 0) {
    DeserializationError err = deserializeJson(docOut, resp);
    if (err) {
      docOut["msg"] = "Resposta invalida do servidor";
    }
  }

  if (code == 401 && exigirSessao) {
    encerrarSessaoLocal("Sessao expirada. Passe o cracha.");
  }
  return code;
}

void sincronizarPingERtc() {
  JsonDocument doc;
  int code = apiRequest("GET", "/api/kiosk/ping", "", doc, false);
  if (code == 200) {
    servidorOK = true;
    long epoch = doc["epoch"] | 0L;
    long tz = doc["tz_offset_s"] | 0L;
    if (rtcOK && epoch > 1700000000L) {
      DateTime agoraSrv((uint32_t)(epoch + tz));
      DateTime agoraRtc = rtc.now();
      long diff = labs((long)agoraSrv.unixtime() - (long)agoraRtc.unixtime());
      if (diff > 5) {
        rtc.adjust(agoraSrv);
      }
    }
  } else {
    servidorOK = false;
  }
}

void enviarHeartbeat() {
  if (WiFi.status() != WL_CONNECTED) return;
  JsonDocument payload;
  payload["id"] = DEVICE_ID;
  payload["tipo"] = "kiosk";
  payload["ip"] = WiFi.localIP().toString();
  payload["firmware"] = FW_VERSION;
  JsonObject info = payload["info"].to<JsonObject>();
  info["rssi"] = WiFi.RSSI();
  info["nfc"] = nfcOK;
  info["rtc"] = rtcOK;
  String body;
  serializeJson(payload, body);
  JsonDocument resp;
  apiRequest("POST", "/api/dispositivos/heartbeat", body, resp, false);
}

void atualizarAulaDoJson(JsonVariant aulaObj) {
  if (aulaObj.isNull()) return;
  aulaAberta = aulaObj["aberta"] | false;
  podeGerenciarAula = aulaObj["pode_gerenciar"] | podeGerenciarAula;
  aulaNome = aulaObj["nome"] | "";
  aulaItensAbertos = aulaObj["itens_abertos"] | 0;
  monitorAutorizado = aulaObj["autorizado"] | true;
  monitorAutorizador = aulaObj["autorizador"] | "";
}

// =====================================================================
// CARREGAMENTO DE DADOS DO SERVIDOR
// =====================================================================
bool carregarInventario(int pagina) {
  JsonDocument doc;
  int code = apiRequest("GET", "/api/kiosk/itens?pagina=" + String(pagina) + "&tam=5", "", doc);
  if (code != 200) {
    if (code != 401) {
      msgStatus = doc["msg"] | "Erro ao carregar inventario";
      msgErro = true;
    }
    return false;
  }
  invPag = doc["pagina"] | 0;
  invPaginas = doc["paginas"] | 1;
  invTotal = doc["total"] | 0;
  invCount = 0;
  JsonArray arr = doc["itens"].as<JsonArray>();
  for (JsonObject it : arr) {
    if (invCount >= 5) break;
    invItens[invCount].nome = it["nome"] | "";
    invItens[invCount].estado = it["estado"] | "";
    invItens[invCount].detalhe = it["detalhe"] | "";
    invCount++;
  }
  return true;
}

bool carregarTipos(int pagina) {
  JsonDocument doc;
  int code = apiRequest("GET", "/api/kiosk/tipos?pagina=" + String(pagina) + "&tam=4", "", doc);
  if (code != 200) {
    if (code != 401) {
      msgStatus = doc["msg"] | "Erro ao carregar tipos";
      msgErro = true;
    }
    return false;
  }
  tiposPag = doc["pagina"] | 0;
  tiposPaginas = doc["paginas"] | 1;
  tiposCount = 0;
  JsonArray arr = doc["tipos"].as<JsonArray>();
  for (JsonObject t : arr) {
    if (tiposCount >= 4) break;
    tiposLista[tiposCount].id = t["id"] | 0;
    tiposLista[tiposCount].nome = t["nome"] | "";
    tiposCount++;
  }
  return true;
}

bool carregarStatusAula() {
  JsonDocument doc;
  int code = apiRequest("GET", "/api/kiosk/aula", "", doc);
  if (code != 200) return false;
  atualizarAulaDoJson(doc["aula"]);
  return true;
}

bool carregarConferencia() {
  JsonDocument doc;
  int code = apiRequest("GET", "/api/kiosk/conferencia", "", doc);
  if (code != 200) return false;
  confAberta = doc["aberta"] | false;
  confTotal = doc["total"] | 0;
  confLidos = doc["lidos"] | 0;
  confEmp = doc["emprestados"] | 0;
  confFaltando = doc["faltando"] | 0;
  return true;
}

// =====================================================================
// DESENHO DAS TELAS
// =====================================================================
void mostrarBoasVindas(const String& nome, const String& perfil) {
  tft.fillScreen(COR_FUNDO);
  desenharCabecalho("ACESSO AUTORIZADO");
  uint16_t cor = (perfil == "PROFESSOR") ? COR_VERDE_OK : (perfil == "ADMIN" ? COR_AZUL : COR_LARANJA);
  tft.drawRoundRect(14, 46, 292, 134, 10, cor);
  tft.setTextColor(COR_BRANCO, COR_FUNDO);
  tft.setTextSize(2);
  tft.setCursor(26, 62);
  tft.print("Bem-vindo(a):");
  tft.setTextColor(cor, COR_FUNDO);
  tft.setTextSize(3);
  tft.setCursor(26, 94);
  tft.print(perfil);
  tft.setTextColor(COR_BRANCO, COR_FUNDO);
  tft.setTextSize(2);
  tft.setCursor(26, 138);
  tft.print(cortar(nome, 22));
  delay(1400);
}

void desenharTelaLogin() {
  telaAtual = TELA_LOGIN;
  tft.fillScreen(COR_FUNDO);
  desenharCabecalho("DEX0199 - LAB MAKER");

  tft.fillRoundRect(12, 42, 296, 86, 8, COR_CARD);
  tft.drawRoundRect(12, 42, 296, 86, 8, COR_AZUL);
  tft.setTextColor(COR_AMARELO, COR_CARD);
  tft.setTextSize(2);
  tft.setCursor(38, 58);
  tft.print("APROXIME O CRACHA");
  tft.setCursor(46, 86);
  tft.print("NFC PARA ENTRAR");

  if (msgStatus.length() > 0) {
    desenharBoxStatus(134, 34);
  }

  tft.setTextSize(1);
  tft.setCursor(12, 174);
  tft.setTextColor(servidorOK ? COR_VERDE_OK : COR_VERMELHO, COR_FUNDO);
  if (WiFi.status() == WL_CONNECTED) {
    tft.print(String("SRV ") + SERVER_HOST + ":" + SERVER_PORT + (servidorOK ? " [OK]" : " [OFFLINE]"));
  } else {
    tft.print("Wi-Fi: DESCONECTADO");
  }

  tft.setCursor(12, 190);
  tft.setTextColor(nfcOK ? COR_VERDE_OK : COR_VERMELHO, COR_FUNDO);
  tft.print(nfcOK ? "NFC PN532: OK" : "NFC PN532: ERRO");
  tft.setTextColor(COR_CINZA, COR_FUNDO);
  tft.print(" | ");
  if (rtcOK) {
    DateTime now = rtc.now();
    char buf[20];
    snprintf(buf, sizeof(buf), "RTC %02d:%02d", now.hour(), now.minute());
    tft.print(buf);
  } else {
    tft.print("RTC: N/A");
  }

  tft.setCursor(12, 206);
  tft.setTextColor(COR_CINZA, COR_FUNDO);
  tft.print("IP CYD: " + (WiFi.status() == WL_CONNECTED ? WiFi.localIP().toString() : String("--")));

  desenharBotao(200, 194, 110, 36, COR_AZUL_ESC, "RECONECTAR", 1);
}

void desenharTelaMenu() {
  telaAtual = TELA_MENU;
  tft.fillScreen(COR_FUNDO);
  desenharCabecalho("MENU PRINCIPAL", true);

  tft.setTextSize(1);
  tft.setTextColor(COR_AMARELO, COR_FUNDO);
  tft.setCursor(10, 38);
  tft.print("[" + usuarioPerfil + "] " + cortar(usuarioNome, 22));

  tft.setCursor(220, 38);
  tft.setTextColor(aulaAberta ? COR_VERDE_OK : COR_CINZA, COR_FUNDO);
  tft.print(aulaAberta ? "AULA: ABERTA" : "SEM AULA");

  // Grade 2x3
  desenharBotao(10,  54, 145, 54, COR_LARANJA,  "EMPRESTIMO", 2);
  desenharBotao(165, 54, 145, 54, aulaAberta ? COR_VERDE : COR_AZUL_ESC, "AULA", 2);

  desenharBotao(10,  116, 145, 54, COR_AZUL_ESC, "INVENTARIO", 2);
  desenharBotao(165, 116, 145, 54, COR_VERDE,    "CADASTRAR",  2);

  desenharBotao(10,  178, 145, 54, COR_VERMELHO, "OCORRENCIA", 2);
  desenharBotao(165, 178, 145, 54, COR_ROXO,     "CONFERIR",   2);
}

void desenharTelaEmprestimo() {
  telaAtual = TELA_EMPRESTIMO;
  tft.fillScreen(COR_FUNDO);
  desenharCabecalho("EMPRESTIMO / DEVOL");

  desenharBotao(10,  40, 145, 38, (modoEmprestimo == "bancada") ? COR_VERDE : COR_CINZA_E,   "BANCADA", 2);
  desenharBotao(165, 40, 145, 38, (modoEmprestimo == "casa")    ? COR_LARANJA : COR_CINZA_E, "CASA",    2);

  tft.setTextColor(COR_BRANCO, COR_FUNDO);
  tft.setTextSize(1);
  tft.setCursor(12, 86);
  tft.print("Aproxime o item (NFC ou QR na camera S3)");
  tft.setCursor(12, 98);
  tft.print("para emprestar ou devolver automaticamente.");

  desenharBoxStatus(114, 70);
  desenharBotao(180, 194, 130, 38, COR_AZUL_ESC, "VOLTAR", 2);
}

void desenharTelaQuantidade() {
  telaAtual = TELA_QUANTIDADE;
  tft.fillScreen(COR_FUNDO);
  desenharCabecalho("QUANTIDADE");

  tft.setTextColor(COR_AMARELO, COR_FUNDO);
  tft.setTextSize(2);
  tft.setCursor(10, 40);
  tft.print(cortar(qtdNome, 24));

  tft.setTextColor(COR_CINZA, COR_FUNDO);
  tft.setTextSize(1);
  tft.setCursor(10, 62);
  tft.print("Disponivel: " + String(qtdDisp) + "/" + String(qtdTotal) + "  | Modo: " + modoEmprestimo);

  desenharBotao(10,  82, 54, 42, COR_CINZA_E, "-5", 2);
  desenharBotao(70,  82, 54, 42, COR_CINZA_E, "-1", 2);

  tft.fillRoundRect(130, 82, 60, 42, 6, COR_CARD);
  tft.drawRoundRect(130, 82, 60, 42, 6, COR_BRANCO);
  tft.setTextColor(COR_AMARELO, COR_CARD);
  tft.setTextSize(2);
  String qStr = String(qtdSel);
  tft.setCursor(160 - qStr.length() * 6, 95);
  tft.print(qStr);

  desenharBotao(196, 82, 54, 42, COR_CINZA_E, "+1", 2);
  desenharBotao(256, 82, 54, 42, COR_CINZA_E, "+5", 2);

  desenharBotao(10,  138, 145, 44, COR_LARANJA, "EMPRESTAR", 2);
  desenharBotao(165, 138, 145, 44, COR_VERDE,   "DEVOLVER",  2);
  desenharBotao(180, 194, 130, 38, COR_AZUL_ESC, "CANCELAR", 2);
}

void desenharTelaAula() {
  telaAtual = TELA_AULA;
  tft.fillScreen(COR_FUNDO);
  desenharCabecalho("GESTAO DE AULA");

  tft.fillRoundRect(10, 40, 300, 66, 7, COR_CARD);
  tft.drawRoundRect(10, 40, 300, 66, 7, aulaAberta ? COR_VERDE_OK : COR_CINZA_E);
  tft.setTextSize(1);
  if (aulaAberta) {
    tft.setTextColor(COR_VERDE_OK, COR_CARD);
    tft.setCursor(18, 48);
    tft.print("AULA EM ANDAMENTO:");
    tft.setTextColor(COR_BRANCO, COR_CARD);
    tft.setCursor(18, 64);
    tft.print(cortar(aulaNome, 44));
    tft.setTextColor(COR_AMARELO, COR_CARD);
    tft.setCursor(18, 82);
    tft.print("Itens em aberto nesta aula: " + String(aulaItensAbertos));
  } else {
    tft.setTextColor(COR_CINZA, COR_CARD);
    tft.setCursor(18, 66);
    tft.print("Nenhuma aula aberta no momento.");
  }

  if (podeGerenciarAula) {
    if (!aulaAberta) {
      desenharBotao(10, 114, 300, 40, COR_VERDE, "INICIAR AULA", 2);
    } else {
      desenharBotao(10,  114, 145, 40, COR_AZUL,     "AUTORIZAR MON", 1);
      desenharBotao(165, 114, 145, 40, COR_VERMELHO, "ENCERRAR AULA", 1);
    }
  } else {
    tft.setTextSize(1);
    tft.setCursor(12, 120);
    tft.setTextColor(monitorAutorizado ? COR_VERDE_OK : COR_AMARELO, COR_FUNDO);
    if (monitorAutorizado) {
      tft.print("Monitor autorizado por: " + cortar(monitorAutorizador, 28));
    } else {
      tft.print("Sem autorizacao de professor (CASA bloqueado).");
    }
  }

  desenharBoxStatus(160, 28);
  desenharBotao(180, 194, 130, 38, COR_AZUL_ESC, "VOLTAR", 2);
}

void desenharTelaAutorizar() {
  telaAtual = TELA_AULA_AUTORIZAR;
  tft.fillScreen(COR_FUNDO);
  desenharCabecalho("AUTORIZAR MONITOR");

  tft.fillRoundRect(12, 46, 296, 80, 8, COR_CARD);
  tft.drawRoundRect(12, 46, 296, 80, 8, COR_AZUL);
  tft.setTextColor(COR_AMARELO, COR_CARD);
  tft.setTextSize(2);
  tft.setCursor(26, 62);
  tft.print("Aproxime o cracha");
  tft.setCursor(26, 90);
  tft.print("NFC do MONITOR");

  desenharBoxStatus(136, 48);
  desenharBotao(180, 194, 130, 38, COR_AZUL_ESC, "VOLTAR", 2);
}

void desenharTelaDecisaoAula() {
  telaAtual = TELA_AULA_DECISAO;
  tft.fillScreen(COR_FUNDO);
  desenharCabecalho("ITENS PENDENTES");

  tft.setTextColor(COR_AMARELO, COR_FUNDO);
  tft.setTextSize(2);
  tft.setCursor(12, 42);
  tft.print(String(aulaPendencias) + " item(ns) sem devolver!");

  tft.setTextColor(COR_BRANCO, COR_FUNDO);
  tft.setTextSize(1);
  tft.setCursor(12, 68);
  tft.print("Como deseja encerrar a aula?");

  desenharBotao(10, 86,  300, 44, COR_LARANJA,  "DEVOLVER DEPOIS (manter emprest.)", 1);
  desenharBotao(10, 138, 300, 44, COR_VERMELHO, "MARCAR COMO PERDIDOS (ocorrencia)", 1);
  desenharBotao(180, 194, 130, 38, COR_AZUL_ESC, "CANCELAR", 2);
}

void desenharTelaFeedback() {
  telaAtual = TELA_AULA_FEEDBACK;
  tft.fillScreen(COR_FUNDO);
  desenharCabecalho("FEEDBACK DA AULA");

  tft.setTextColor(COR_AMARELO, COR_FUNDO);
  tft.setTextSize(2);
  tft.setCursor(20, 46);
  tft.print("Como foi a aula hoje?");

  const uint16_t cores[5] = { COR_VERMELHO, COR_LARANJA, COR_CINZA, COR_AZUL, COR_VERDE };
  const char* labels[5] = { "1", "2", "3", "4", "5" };
  for (int i = 0; i < 5; i++) {
    desenharBotao(10 + i * 61, 84, 56, 56, cores[i], labels[i], 3);
  }

  tft.setTextColor(COR_CINZA, COR_FUNDO);
  tft.setTextSize(1);
  tft.setCursor(10, 148);
  tft.print("1 = Muito ruim                  5 = Muito bom");

  desenharBoxStatus(164, 24);
  desenharBotao(180, 194, 130, 38, COR_AZUL_ESC, "CANCELAR", 2);
}

void desenharTelaInventario() {
  telaAtual = TELA_INVENTARIO;
  tft.fillScreen(COR_FUNDO);
  char tit[32];
  snprintf(tit, sizeof(tit), "INVENTARIO %d/%d", invPag + 1, invPaginas);
  desenharCabecalho(tit);

  tft.setTextSize(1);
  if (invCount == 0) {
    tft.setTextColor(COR_CINZA, COR_FUNDO);
    tft.setCursor(16, 56);
    tft.print("Nenhum item cadastrado.");
  } else {
    for (int i = 0; i < invCount; i++) {
      int y = 40 + i * 22;
      String est = invItens[i].estado;
      uint16_t c = COR_CINZA;
      const char* tag = "[OUTR] ";
      if (est == "disponivel") { c = COR_VERDE_OK; tag = "[DISP] "; }
      else if (est == "emprestado") { c = COR_AMARELO; tag = "[EMPR] "; }
      else if (est == "manutencao") { c = COR_LARANJA; tag = "[MANU] "; }
      else if (est == "perdido") { c = COR_VERMELHO; tag = "[PERD] "; }
      else if (est == "quantidade") { c = COR_AZUL; tag = "[QTD ] "; }

      tft.setCursor(10, y);
      tft.setTextColor(c, COR_FUNDO);
      tft.print(tag);
      tft.setTextColor(COR_BRANCO, COR_FUNDO);
      String linha = invItens[i].nome;
      if (invItens[i].detalhe.length() > 0) linha += " (" + invItens[i].detalhe + ")";
      tft.print(cortar(linha, 41));
    }
  }

  desenharBoxStatus(152, 34);
  desenharBotao(10,  194, 85,  38, (invPag > 0) ? COR_AZUL_ESC : COR_CINZA_E, "< ANT",  2);
  desenharBotao(102, 194, 92,  38, (invPag + 1 < invPaginas) ? COR_AZUL_ESC : COR_CINZA_E, "PROX >", 2);
  desenharBotao(202, 194, 108, 38, COR_AZUL_ESC, "VOLTAR", 2);
}

void desenharTelaCadTipo() {
  telaAtual = TELA_CAD_TIPO;
  tft.fillScreen(COR_FUNDO);
  char tit[32];
  snprintf(tit, sizeof(tit), "TIPO (%d/%d)", tiposPag + 1, tiposPaginas);
  desenharCabecalho(tit);

  for (int i = 0; i < tiposCount; i++) {
    int y = 40 + i * 36;
    desenharBotao(10, y, 300, 30, COR_CARD, cortar(tiposLista[i].nome, 36).c_str(), 1);
  }
  if (tiposCount == 0) {
    tft.setTextColor(COR_CINZA, COR_FUNDO);
    tft.setTextSize(1);
    tft.setCursor(12, 60);
    tft.print("Nenhum tipo individual. Crie pelo painel web.");
  }

  desenharBotao(10,  194, 85,  38, (tiposPag > 0) ? COR_AZUL_ESC : COR_CINZA_E, "< ANT", 2);
  desenharBotao(102, 194, 92,  38, (tiposPag + 1 < tiposPaginas) ? COR_AZUL_ESC : COR_CINZA_E, "PROX >", 2);
  desenharBotao(202, 194, 108, 38, COR_AZUL_ESC, "VOLTAR", 2);
}

void desenharTelaCadLer() {
  telaAtual = TELA_CAD_LER;
  tft.fillScreen(COR_FUNDO);
  desenharCabecalho("CADASTRAR ITEM");

  tft.setTextColor(COR_AMARELO, COR_FUNDO);
  tft.setTextSize(2);
  tft.setCursor(10, 42);
  tft.print(cortar(tipoSelecionadoNome, 24));

  tft.setTextColor(COR_BRANCO, COR_FUNDO);
  tft.setTextSize(1);
  tft.setCursor(10, 68);
  tft.print("Aproxime Tag NFC ou leia QR Code na S3:");

  desenharBoxStatus(86, 94);
  desenharBotao(10,  194, 150, 38, COR_CINZA_E,  "TROCAR TIPO", 1);
  desenharBotao(170, 194, 140, 38, COR_AZUL_ESC, "VOLTAR",      2);
}

void desenharTelaOcorrencia() {
  telaAtual = TELA_OCORRENCIA;
  tft.fillScreen(COR_FUNDO);
  desenharCabecalho("OCORRENCIA");

  desenharBotao(10,  38, 72, 34, (tipoOcorrencia == "danificado") ? COR_LARANJA  : COR_CINZA_E, "DANIF", 1);
  desenharBotao(86,  38, 72, 34, (tipoOcorrencia == "perdido")    ? COR_VERMELHO : COR_CINZA_E, "PERD",  1);
  desenharBotao(162, 38, 72, 34, (tipoOcorrencia == "encontrado") ? COR_VERDE    : COR_CINZA_E, "ENCON", 1);
  desenharBotao(238, 38, 72, 34, (tipoOcorrencia == "furto")      ? COR_ROXO     : COR_CINZA_E, "FURTO", 1);

  tft.setTextColor(COR_BRANCO, COR_FUNDO);
  tft.setTextSize(1);
  tft.setCursor(12, 82);
  tft.print("Tipo: " + tipoOcorrencia + " | Aproxime item (NFC ou QR S3):");

  desenharBoxStatus(100, 82);
  desenharBotao(180, 194, 130, 38, COR_AZUL_ESC, "VOLTAR", 2);
}

void desenharTelaConferencia() {
  telaAtual = TELA_CONFERENCIA;
  tft.fillScreen(COR_FUNDO);
  desenharCabecalho("CONFERENCIA");

  if (!confAberta) {
    tft.setTextColor(COR_CINZA, COR_FUNDO);
    tft.setTextSize(1);
    tft.setCursor(12, 54);
    tft.print("Nenhuma conferencia aberta no momento.");
    desenharBotao(10, 80, 300, 44, COR_VERDE, "INICIAR CONFERENCIA", 2);
    desenharBoxStatus(134, 48);
    desenharBotao(180, 194, 130, 38, COR_AZUL_ESC, "VOLTAR", 2);
  } else {
    tft.fillRoundRect(10, 38, 300, 62, 7, COR_CARD);
    tft.drawRoundRect(10, 38, 300, 62, 7, COR_ROXO);
    tft.setTextColor(COR_AMARELO, COR_CARD);
    tft.setTextSize(2);
    tft.setCursor(18, 46);
    tft.print("Lidos: " + String(confLidos) + " / " + String(confTotal));
    tft.setTextColor(COR_BRANCO, COR_CARD);
    tft.setTextSize(1);
    tft.setCursor(18, 74);
    tft.print("Emprestados: " + String(confEmp) + "  |  Faltando: " + String(confFaltando));

    tft.setTextColor(COR_CINZA, COR_FUNDO);
    tft.setCursor(12, 106);
    tft.print("Leia cada item via NFC ou QR na S3:");

    desenharBoxStatus(120, 64);
    desenharBotao(10,  194, 150, 38, COR_VERMELHO, "ENCERRAR", 2);
    desenharBotao(170, 194, 140, 38, COR_AZUL_ESC, "VOLTAR",   2);
  }
}

// =====================================================================
// ACOES DE NEGOCIO (NFC / QR / BOTOES)
// =====================================================================
void renovarAtividade() {
  inicioAtividade = millis();
}

void realizarLogin(const String& uid) {
  JsonDocument payload;
  payload["tag"] = uid;
  String body;
  serializeJson(payload, body);

  JsonDocument resp;
  int code = apiRequest("POST", "/api/kiosk/login", body, resp, false);
  if (code == 200 && (resp["ok"] | false)) {
    sessaoToken = resp["token"] | "";
    usuarioNome = resp["usuario"]["nome"] | "";
    usuarioPerfil = resp["perfil"] | "";
    sessaoTtlMs = (unsigned long)(resp["ttl_s"] | 300) * 1000UL;
    atualizarAulaDoJson(resp["aula"]);
    renovarAtividade();
    msgStatus = "";
    msgErro = false;
    mostrarBoasVindas(usuarioNome, usuarioPerfil);
    desenharTelaMenu();
  } else {
    String m = resp["msg"] | "Erro de autenticacao";
    msgStatus = m + " (" + uid + ")";
    msgErro = true;
    desenharTelaLogin();
  }
}

void processarCodigo(const String& codigo, const String& origem) {
  renovarAtividade();

  if (telaAtual == TELA_EMPRESTIMO) {
    JsonDocument payload;
    payload["codigo"] = codigo;
    payload["origem"] = origem;
    payload["modalidade"] = modoEmprestimo;
    payload["operacao"] = "auto";
    String body;
    serializeJson(payload, body);

    JsonDocument resp;
    int code = apiRequest("POST", "/api/kiosk/movimentar", body, resp);
    if (code == 401) return;
    if (code == 200 && String(resp["acao"] | "") == "precisa_quantidade") {
      qtdCodigo = codigo;
      qtdOrigem = origem;
      qtdNome = resp["tipo"]["nome"] | codigo;
      qtdDisp = resp["tipo"]["qntd_disponivel"] | 0;
      qtdTotal = resp["tipo"]["qntd_total"] | 0;
      qtdSel = 1;
      desenharTelaQuantidade();
      return;
    }
    msgStatus = resp["msg"] | "Erro ao movimentar";
    msgErro = (code != 200);
    desenharTelaEmprestimo();
  }
  else if (telaAtual == TELA_CAD_LER) {
    JsonDocument payload;
    payload["codigo"] = codigo;
    payload["origem"] = origem;
    payload["tipo_id"] = tipoSelecionadoId;
    String body;
    serializeJson(payload, body);

    JsonDocument resp;
    int code = apiRequest("POST", "/api/kiosk/cadastrar", body, resp);
    if (code == 401) return;
    msgStatus = resp["msg"] | "Erro ao cadastrar";
    msgErro = (code != 200);
    desenharTelaCadLer();
  }
  else if (telaAtual == TELA_OCORRENCIA) {
    JsonDocument payload;
    payload["codigo"] = codigo;
    payload["origem"] = origem;
    payload["tipo"] = tipoOcorrencia;
    payload["quantidade"] = 1;
    String body;
    serializeJson(payload, body);

    JsonDocument resp;
    int code = apiRequest("POST", "/api/kiosk/ocorrencia", body, resp);
    if (code == 401) return;
    msgStatus = resp["msg"] | "Erro ao registrar ocorrencia";
    msgErro = (code != 200);
    desenharTelaOcorrencia();
  }
  else if (telaAtual == TELA_CONFERENCIA && confAberta) {
    JsonDocument payload;
    payload["codigo"] = codigo;
    payload["origem"] = origem;
    String body;
    serializeJson(payload, body);

    JsonDocument resp;
    int code = apiRequest("POST", "/api/kiosk/conferencia/ler", body, resp);
    if (code == 401) return;
    if (code == 200) {
      confTotal = resp["total"] | confTotal;
      confLidos = resp["lidos"] | confLidos;
      confEmp = resp["emprestados"] | confEmp;
      confFaltando = resp["faltando"] | confFaltando;
    }
    msgStatus = resp["msg"] | "Erro na leitura";
    msgErro = (code != 200);
    desenharTelaConferencia();
  }
  else if (telaAtual == TELA_INVENTARIO) {
    JsonDocument resp;
    int code = apiRequest("GET", "/api/kiosk/consulta?codigo=" + urlEncode(codigo), "", resp);
    if (code == 401) return;
    msgStatus = resp["msg"] | "Erro na consulta";
    msgErro = (code != 200 || !(resp["encontrado"] | false));
    desenharTelaInventario();
  }
  else if (telaAtual == TELA_AULA_AUTORIZAR && origem == "nfc") {
    JsonDocument payload;
    payload["tag"] = codigo;
    String body;
    serializeJson(payload, body);

    JsonDocument resp;
    int code = apiRequest("POST", "/api/kiosk/aula/autorizar", body, resp);
    if (code == 401) return;
    msgStatus = resp["msg"] | "Erro ao autorizar monitor";
    msgErro = (code != 200);
    desenharTelaAutorizar();
  }
}

void enviarMovimentacaoQuantidade(const char* operacao) {
  JsonDocument payload;
  payload["codigo"] = qtdCodigo;
  payload["origem"] = qtdOrigem;
  payload["modalidade"] = modoEmprestimo;
  payload["operacao"] = operacao;
  payload["quantidade"] = qtdSel;
  String body;
  serializeJson(payload, body);

  JsonDocument resp;
  int code = apiRequest("POST", "/api/kiosk/movimentar", body, resp);
  if (code == 401) return;
  msgStatus = resp["msg"] | "Erro";
  msgErro = (code != 200);
  desenharTelaEmprestimo();
}

void enviarEncerramentoAula(int nota) {
  JsonDocument payload;
  payload["decisao"] = aulaDecisao;
  payload["feedback"] = nota;
  String body;
  serializeJson(payload, body);

  JsonDocument resp;
  int code = apiRequest("POST", "/api/kiosk/aula/encerrar", body, resp);
  if (code == 401) return;
  if (code == 200) {
    aulaAberta = false;
    aulaNome = "";
    aulaItensAbertos = 0;
    msgStatus = resp["msg"] | "Aula encerrada";
    msgErro = false;
    desenharTelaAula();
  } else {
    msgStatus = resp["msg"] | "Erro ao encerrar aula";
    msgErro = true;
    desenharTelaFeedback();
  }
}

// =====================================================================
// TOUCHSCREEN
// =====================================================================
void processarToque() {
  if (!ts.tirqTouched() || !ts.touched()) return;
  if (millis() - ultimoToque < 280) return;

  TS_Point p = ts.getPoint();
  ultimoToque = millis();

  int x = constrain(map(p.x, TOUCH_MIN_X, TOUCH_MAX_X, 0, 320), 0, 319);
  int y = constrain(map(p.y, TOUCH_MIN_Y, TOUCH_MAX_Y, 0, 240), 0, 239);

  if (telaAtual == TELA_LOGIN) {
    if (dentro(x, y, 200, 194, 110, 36)) {
      if (WiFi.status() != WL_CONNECTED) {
        WiFi.reconnect();
        delay(600);
      }
      sincronizarPingERtc();
      msgStatus = servidorOK ? "Servidor conectado!" : "Servidor inacessivel";
      msgErro = !servidorOK;
      desenharTelaLogin();
    }
    return;
  }

  renovarAtividade();

  if (telaAtual == TELA_MENU) {
    // SAIR no cabecalho
    if (dentro(x, y, 250, 0, 70, 34)) {
      JsonDocument resp;
      apiRequest("POST", "/api/kiosk/logout", "{}", resp);
      encerrarSessaoLocal("");
      return;
    }
    if (dentro(x, y, 10, 54, 145, 54)) {
      msgStatus = "Pronto para leitura.";
      msgErro = false;
      desenharTelaEmprestimo();
    } else if (dentro(x, y, 165, 54, 145, 54)) {
      msgStatus = "";
      msgErro = false;
      if (carregarStatusAula()) desenharTelaAula();
    } else if (dentro(x, y, 10, 116, 145, 54)) {
      msgStatus = "Aproxime NFC/QR para consultar um item.";
      msgErro = false;
      if (carregarInventario(0)) desenharTelaInventario();
    } else if (dentro(x, y, 165, 116, 145, 54)) {
      msgStatus = "";
      msgErro = false;
      if (carregarTipos(0)) desenharTelaCadTipo();
    } else if (dentro(x, y, 10, 178, 145, 54)) {
      msgStatus = "Selecione o tipo e aproxime o item.";
      msgErro = false;
      desenharTelaOcorrencia();
    } else if (dentro(x, y, 165, 178, 145, 54)) {
      msgStatus = "";
      msgErro = false;
      if (carregarConferencia()) desenharTelaConferencia();
    }
  }
  else if (telaAtual == TELA_EMPRESTIMO) {
    if (dentro(x, y, 10, 40, 145, 38)) {
      modoEmprestimo = "bancada";
      msgStatus = "Modo: BANCADA";
      msgErro = false;
      desenharTelaEmprestimo();
    } else if (dentro(x, y, 165, 40, 145, 38)) {
      modoEmprestimo = "casa";
      msgStatus = "Modo: CASA";
      msgErro = false;
      desenharTelaEmprestimo();
    } else if (dentro(x, y, 180, 194, 130, 38)) {
      desenharTelaMenu();
    }
  }
  else if (telaAtual == TELA_QUANTIDADE) {
    if (dentro(x, y, 10, 82, 54, 42)) { qtdSel = max(1, qtdSel - 5); desenharTelaQuantidade(); }
    else if (dentro(x, y, 70, 82, 54, 42)) { qtdSel = max(1, qtdSel - 1); desenharTelaQuantidade(); }
    else if (dentro(x, y, 196, 82, 54, 42)) { qtdSel = min(max(1, qtdTotal), qtdSel + 1); desenharTelaQuantidade(); }
    else if (dentro(x, y, 256, 82, 54, 42)) { qtdSel = min(max(1, qtdTotal), qtdSel + 5); desenharTelaQuantidade(); }
    else if (dentro(x, y, 10, 138, 145, 44)) { enviarMovimentacaoQuantidade("emprestar"); }
    else if (dentro(x, y, 165, 138, 145, 44)) { enviarMovimentacaoQuantidade("devolver"); }
    else if (dentro(x, y, 180, 194, 130, 38)) { desenharTelaEmprestimo(); }
  }
  else if (telaAtual == TELA_AULA) {
    if (podeGerenciarAula && !aulaAberta && dentro(x, y, 10, 114, 300, 40)) {
      JsonDocument resp;
      int code = apiRequest("POST", "/api/kiosk/aula/iniciar", "{}", resp);
      if (code == 401) return;
      atualizarAulaDoJson(resp["aula"]);
      msgStatus = resp["msg"] | "Erro";
      msgErro = (code != 200);
      desenharTelaAula();
    } else if (podeGerenciarAula && aulaAberta && dentro(x, y, 10, 114, 145, 40)) {
      msgStatus = "Aguardando cracha do monitor...";
      msgErro = false;
      desenharTelaAutorizar();
    } else if (podeGerenciarAula && aulaAberta && dentro(x, y, 165, 114, 145, 40)) {
      carregarStatusAula();
      msgStatus = "";
      msgErro = false;
      if (aulaItensAbertos > 0) {
        aulaPendencias = aulaItensAbertos;
        desenharTelaDecisaoAula();
      } else {
        aulaDecisao = "sem_pendencia";
        desenharTelaFeedback();
      }
    } else if (dentro(x, y, 180, 194, 130, 38)) {
      desenharTelaMenu();
    }
  }
  else if (telaAtual == TELA_AULA_AUTORIZAR) {
    if (dentro(x, y, 180, 194, 130, 38)) {
      msgStatus = "";
      if (carregarStatusAula()) desenharTelaAula();
    }
  }
  else if (telaAtual == TELA_AULA_DECISAO) {
    if (dentro(x, y, 10, 86, 300, 44)) {
      aulaDecisao = "devolver_depois";
      desenharTelaFeedback();
    } else if (dentro(x, y, 10, 138, 300, 44)) {
      aulaDecisao = "com_pendencia";
      desenharTelaFeedback();
    } else if (dentro(x, y, 180, 194, 130, 38)) {
      desenharTelaAula();
    }
  }
  else if (telaAtual == TELA_AULA_FEEDBACK) {
    for (int i = 0; i < 5; i++) {
      if (dentro(x, y, 10 + i * 61, 84, 56, 56)) {
        enviarEncerramentoAula(i + 1);
        return;
      }
    }
    if (dentro(x, y, 180, 194, 130, 38)) {
      desenharTelaAula();
    }
  }
  else if (telaAtual == TELA_INVENTARIO) {
    if (dentro(x, y, 10, 194, 85, 38) && invPag > 0) {
      if (carregarInventario(invPag - 1)) desenharTelaInventario();
    } else if (dentro(x, y, 102, 194, 92, 38) && invPag + 1 < invPaginas) {
      if (carregarInventario(invPag + 1)) desenharTelaInventario();
    } else if (dentro(x, y, 202, 194, 108, 38)) {
      desenharTelaMenu();
    }
  }
  else if (telaAtual == TELA_CAD_TIPO) {
    for (int i = 0; i < tiposCount; i++) {
      if (dentro(x, y, 10, 40 + i * 36, 300, 30)) {
        tipoSelecionadoId = tiposLista[i].id;
        tipoSelecionadoNome = tiposLista[i].nome;
        msgStatus = "Aguardando leitura...";
        msgErro = false;
        desenharTelaCadLer();
        return;
      }
    }
    if (dentro(x, y, 10, 194, 85, 38) && tiposPag > 0) {
      if (carregarTipos(tiposPag - 1)) desenharTelaCadTipo();
    } else if (dentro(x, y, 102, 194, 92, 38) && tiposPag + 1 < tiposPaginas) {
      if (carregarTipos(tiposPag + 1)) desenharTelaCadTipo();
    } else if (dentro(x, y, 202, 194, 108, 38)) {
      desenharTelaMenu();
    }
  }
  else if (telaAtual == TELA_CAD_LER) {
    if (dentro(x, y, 10, 194, 150, 38)) {
      if (carregarTipos(tiposPag)) desenharTelaCadTipo();
    } else if (dentro(x, y, 170, 194, 140, 38)) {
      desenharTelaMenu();
    }
  }
  else if (telaAtual == TELA_OCORRENCIA) {
    if (dentro(x, y, 10, 38, 72, 34))       { tipoOcorrencia = "danificado"; desenharTelaOcorrencia(); }
    else if (dentro(x, y, 86, 38, 72, 34))  { tipoOcorrencia = "perdido";    desenharTelaOcorrencia(); }
    else if (dentro(x, y, 162, 38, 72, 34)) { tipoOcorrencia = "encontrado"; desenharTelaOcorrencia(); }
    else if (dentro(x, y, 238, 38, 72, 34)) { tipoOcorrencia = "furto";      desenharTelaOcorrencia(); }
    else if (dentro(x, y, 180, 194, 130, 38)) { desenharTelaMenu(); }
  }
  else if (telaAtual == TELA_CONFERENCIA) {
    if (!confAberta && dentro(x, y, 10, 80, 300, 44)) {
      JsonDocument resp;
      int code = apiRequest("POST", "/api/kiosk/conferencia/iniciar", "{}", resp);
      if (code == 401) return;
      if (code == 200) {
        confAberta = resp["aberta"] | true;
        confTotal = resp["total"] | 0;
        confLidos = resp["lidos"] | 0;
        confEmp = resp["emprestados"] | 0;
        confFaltando = resp["faltando"] | 0;
      }
      msgStatus = resp["msg"] | "Conferencia iniciada";
      msgErro = (code != 200);
      desenharTelaConferencia();
    } else if (confAberta && dentro(x, y, 10, 194, 150, 38)) {
      JsonDocument resp;
      int code = apiRequest("POST", "/api/kiosk/conferencia/encerrar", "{}", resp);
      if (code == 401) return;
      if (code == 200) confAberta = false;
      msgStatus = resp["msg"] | "Conferencia encerrada";
      msgErro = (code != 200);
      desenharTelaConferencia();
    } else if (dentro(x, y, 170, 194, 140, 38)) {
      desenharTelaMenu();
    }
  }
}

// =====================================================================
// POLLING DE QR CODES DA ESTACAO OPTICA (ESP32-S3 -> SERVIDOR -> CYD)
// =====================================================================
bool telaAceitaQR() {
  return telaAtual == TELA_EMPRESTIMO ||
         telaAtual == TELA_CAD_LER ||
         telaAtual == TELA_OCORRENCIA ||
         telaAtual == TELA_INVENTARIO ||
         (telaAtual == TELA_CONFERENCIA && confAberta);
}

void verificarFilaQR() {
  if (!telaAceitaQR() || WiFi.status() != WL_CONNECTED) return;
  if (millis() - ultimoPollQR < POLL_QR_MS) return;
  ultimoPollQR = millis();

  JsonDocument resp;
  int code = apiRequest("GET", "/api/kiosk/leitura", "", resp, false);
  if (code == 200 && !resp["codigo"].isNull()) {
    String codigo = resp["codigo"] | "";
    String origem = resp["origem"] | "qr";
    if (codigo.length() > 0) {
      Serial.println("[QR S3] Recebido via servidor: " + codigo);
      processarCodigo(codigo, origem);
    }
  }
}

// =====================================================================
// SETUP & LOOP
// =====================================================================
void setup() {
  Serial.begin(115200);
  Serial.println("\n[DEX0199] Iniciando Terminal Kiosk (CYD)...");

  pinMode(TFT_BL, OUTPUT);
  digitalWrite(TFT_BL, HIGH);
  tft.init();
  tft.setRotation(1);
  tft.fillScreen(COR_FUNDO);
  desenharCabecalho("DEX0199 - INICIANDO");
  tft.setTextColor(COR_BRANCO, COR_FUNDO);
  tft.setTextSize(1);
  tft.setCursor(12, 50);
  tft.print("Inicializando touch, NFC e Wi-Fi...");

  touchSPI.begin(XPT2046_CLK, XPT2046_MISO, XPT2046_MOSI, XPT2046_CS);
  ts.begin(touchSPI);
  ts.setRotation(1);

  I2CExt.begin(I2C_SDA, I2C_SCL, 100000);
  rtcOK = rtc.begin(&I2CExt);
  Serial.println(rtcOK ? "[RTC] DS3231 detectado." : "[RTC] Nao detectado (opcional).");

  nfc.begin();
  uint32_t ver = nfc.getFirmwareVersion();
  if (ver != 0) {
    nfc.SAMConfig();
    nfcOK = true;
    Serial.printf("[NFC] PN532 OK (v%d.%d)\n", (ver >> 16) & 0xFF, (ver >> 8) & 0xFF);
  } else {
    Serial.println("[NFC] PN532 nao respondeu no barramento I2C (SDA=27, SCL=22).");
  }

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  unsigned long t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 10000) {
    delay(250);
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("[WiFi] Conectado! IP: " + WiFi.localIP().toString());
    sincronizarPingERtc();
    enviarHeartbeat();
  } else {
    Serial.println("[WiFi] Nao conectou no boot.");
  }

  desenharTelaLogin();
}

void loop() {
  // Heartbeat periodico
  if (millis() - ultimoHeartbeat >= HEARTBEAT_MS) {
    ultimoHeartbeat = millis();
    if (WiFi.status() == WL_CONNECTED) {
      enviarHeartbeat();
    } else {
      WiFi.reconnect();
    }
  }

  // Expiracao local da sessao (TTL sincronizado com o servidor)
  if (telaAtual != TELA_LOGIN && (millis() - inicioAtividade > sessaoTtlMs)) {
    encerrarSessaoLocal("Sessao expirada por inatividade.");
  }

  // Touch
  processarToque();

  // Polling de QR Codes lidos pela ESP32-S3
  verificarFilaQR();

  // Leitura NFC
  if (nfcOK && (millis() - ultimoNFC >= NFC_COOLDOWN_MS)) {
    uint8_t uid[7];
    uint8_t uidLen = 0;
    if (nfc.readPassiveTargetID(PN532_MIFARE_ISO14443A, uid, &uidLen, 50)) {
      ultimoNFC = millis();
      String uidTxt = formatarUID(uid, uidLen);
      Serial.println("[NFC] Tag lida: " + uidTxt);
      if (telaAtual == TELA_LOGIN) {
        realizarLogin(uidTxt);
      } else {
        processarCodigo(uidTxt, "nfc");
      }
    }
  }
}
