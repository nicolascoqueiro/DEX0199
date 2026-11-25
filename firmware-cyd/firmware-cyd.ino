#include <Wire.h>
#include <SPI.h>
#include <WiFi.h>
#include <WebServer.h>
#include <TFT_eSPI.h>
#include <XPT2046_Touchscreen.h>
#include <Adafruit_PN532.h>

// ===== CONFIGURACAO WI-FI =====
const char* WIFI_SSID = "SEU_WIFI_AQUI";
const char* WIFI_PASS = "SUA_SENHA_AQUI";

WebServer server(80);

// ===== PINOS HARDWARE CYD (ESP32-2432S028) =====
#define TFT_BL 21

// Touchscreen XPT2046 (SPI dedicado na CYD)
#define XPT2046_IRQ  36
#define XPT2046_MOSI 32
#define XPT2046_MISO 39
#define XPT2046_CLK  25
#define XPT2046_CS   33

// NFC Elechouse PN532 V3 (I2C dedicado no conector CN1)
#define NFC_SDA 27
#define NFC_SCL 22

// ===== INSTANCIAS =====
TFT_eSPI tft = TFT_eSPI();
SPIClass touchSPI = SPIClass(VSPI);
XPT2046_Touchscreen ts(XPT2046_CS, XPT2046_IRQ);

TwoWire I2CNFC = TwoWire(1);
Adafruit_PN532 nfc(-1, -1, &I2CNFC);

// ===== CORES (RGB565) =====
#define FUNDO     0x10A2
#define AZUL      0x2D7F
#define AZUL_ESC  0x192B
#define BRANCO    0xFFFF
#define VERDE     0x07E0
#define VERMELHO  0xF800
#define AMARELO   0xFFE0
#define LARANJA   0xFD20
#define CINZA     0x8410

// ===== CREDENCIAIS AUTORIZADAS =====
struct Usuario {
  uint8_t uid[4];
  const char* nome;
  const char* perfil; // "PROFESSOR" ou "MONITOR"
};

const Usuario usuariosAutorizados[] = {
  { {0x4D, 0x87, 0x4E, 0x07}, "Prof. Responsavel", "PROFESSOR" },
  { {0xC0, 0x3E, 0x35, 0x5C}, "Monitor Lab",       "MONITOR"   }
};
const int TOTAL_USUARIOS = sizeof(usuariosAutorizados) / sizeof(usuariosAutorizados[0]);

// ===== ESTRUTURA DE INVENTARIO E EMPRESTIMO =====
enum StatusItem {
  DISP,
  EMP_BANCADA,
  EMP_CASA
};

struct ItemLab {
  String codigo;
  String tipo;
  StatusItem status;
  String responsavel;
};

#define MAX_ITENS 20
ItemLab inventario[MAX_ITENS];
int totalItens = 0;

// ===== ESTADO DA SESSAO E NAVEGACAO =====
enum TelaAtual {
  TELA_LOGIN,
  TELA_MENU,
  TELA_INVENTARIO,
  TELA_CADASTRAR,
  TELA_EMPRESTIMO
};

TelaAtual telaAtual = TELA_LOGIN;
StatusItem modoEmprestimo = EMP_BANCADA;
String usuarioLogado = "";
String perfilLogado = "";
unsigned long inicioSessao = 0;
const unsigned long SESSAO_TTL_MS = 120000; // 2 minutos

String ultimoCodigoRecebidoS3 = "";
unsigned long ultimoToque = 0;
bool nfcOK = false;

// ===== FUNCOES AUXILIARES =====
String formatarUID(uint8_t *uid, uint8_t tamanho) {
  String resultado = "";
  for (uint8_t i = 0; i < tamanho; i++) {
    if (uid[i] < 0x10) resultado += "0";
    resultado += String(uid[i], HEX);
    if (i < tamanho - 1) resultado += ":";
  }
  resultado.toUpperCase();
  return resultado;
}

int buscarIndiceUsuario(uint8_t *uid, uint8_t tamanho) {
  if (tamanho != 4) return -1;
  for (int i = 0; i < TOTAL_USUARIOS; i++) {
    if (memcmp(uid, usuariosAutorizados[i].uid, 4) == 0) {
      return i;
    }
  }
  return -1;
}

int buscarIndiceItem(String codigo) {
  for (int i = 0; i < totalItens; i++) {
    if (inventario[i].codigo == codigo) return i;
  }
  return -1;
}

void renovarSessao() {
  inicioSessao = millis();
}

// ===== DESENHO DAS TELAS =====
void desenharCabecalho(const char* titulo) {
  tft.fillRect(0, 0, 320, 36, AZUL);
  tft.setTextColor(BRANCO, AZUL);
  tft.setTextSize(2);
  tft.setCursor(10, 10);
  tft.print(titulo);
}

void desenharBotao(int x, int y, int w, int h, uint16_t cor, const char* texto) {
  tft.fillRoundRect(x, y, w, h, 8, cor);
  tft.drawRoundRect(x, y, w, h, 8, BRANCO);
  tft.setTextColor(BRANCO, cor);
  tft.setTextSize(2);
  int textX = x + (w - (strlen(texto) * 12)) / 2;
  int textY = y + (h - 16) / 2;
  tft.setCursor(max(x + 6, textX), textY);
  tft.print(texto);
}

void mostrarBoasVindasPerfil(String nome, String perfil) {
  tft.fillScreen(FUNDO);
  desenharCabecalho("ACESSO AUTORIZADO");

  uint16_t corDestaque = (perfil == "PROFESSOR") ? VERDE : LARANJA;

  tft.drawRoundRect(15, 50, 290, 130, 10, corDestaque);

  tft.setTextColor(BRANCO, FUNDO);
  tft.setTextSize(2);
  tft.setCursor(28, 70);
  tft.print("Voce esta acessando");
  tft.setCursor(28, 95);
  tft.print("como:");

  tft.setTextColor(corDestaque, FUNDO);
  tft.setTextSize(3);
  tft.setCursor(28, 128);
  tft.print(perfil);

  tft.setTextColor(CINZA, FUNDO);
  tft.setTextSize(1);
  tft.setCursor(15, 200);
  tft.print("Usuario: " + nome + " | Carregando menu...");

  delay(2200);
}

void desenharTelaLogin() {
  telaAtual = TELA_LOGIN;
  tft.fillScreen(FUNDO);
  desenharCabecalho("LABORATORIO MAKER");

  tft.drawRoundRect(15, 50, 290, 110, 10, BRANCO);
  tft.setTextColor(AMARELO, FUNDO);
  tft.setTextSize(2);
  tft.setCursor(35, 75);
  tft.print("APROXIME O CRACHA");
  tft.setCursor(35, 105);
  tft.print("NFC PARA ENTRAR");

  tft.setTextColor(CINZA, FUNDO);
  tft.setTextSize(1);
  tft.setCursor(15, 180);
  if (WiFi.status() == WL_CONNECTED) {
    tft.print("IP CYD (para S3): " + WiFi.localIP().toString());
  } else {
    tft.print("Wi-Fi: Modo Offline");
  }
  tft.setCursor(15, 200);
  tft.print(nfcOK ? "NFC PN532: Pronto" : "NFC PN532: Erro de comunicacao");
}

void desenharTelaMenu() {
  telaAtual = TELA_MENU;
  tft.fillScreen(FUNDO);
  desenharCabecalho("MENU PRINCIPAL");

  tft.setTextColor(AMARELO, FUNDO);
  tft.setTextSize(1);
  tft.setCursor(12, 44);
  tft.print("[" + perfilLogado + "] " + usuarioLogado);

  desenharBotao(15, 65, 138, 65, AZUL_ESC, "INVENTARIO");
  desenharBotao(167, 65, 138, 65, VERDE, "CADASTRAR");
  desenharBotao(15, 145, 138, 65, LARANJA, "EMPRESTIMO");
  desenharBotao(167, 145, 138, 65, VERMELHO, "SAIR");
}

void desenharTelaInventario() {
  telaAtual = TELA_INVENTARIO;
  tft.fillScreen(FUNDO);
  desenharCabecalho("INVENTARIO");

  tft.setTextSize(1);

  if (totalItens == 0) {
    tft.setTextColor(BRANCO, FUNDO);
    tft.setCursor(20, 60);
    tft.setTextSize(2);
    tft.print("Nenhum item cadastrado.");
  } else {
    int limite = min(totalItens, 5);
    for (int i = 0; i < limite; i++) {
      int y = 48 + (i * 26);
      tft.setCursor(12, y);

      if (inventario[i].status == DISP) {
        tft.setTextColor(VERDE, FUNDO);
        tft.print("[DISP] ");
      } else if (inventario[i].status == EMP_BANCADA) {
        tft.setTextColor(AMARELO, FUNDO);
        tft.print("[BANC] ");
      } else {
        tft.setTextColor(VERMELHO, FUNDO);
        tft.print("[CASA] ");
      }

      tft.setTextColor(BRANCO, FUNDO);
      tft.print(inventario[i].codigo);
    }
  }

  desenharBotao(15, 185, 135, 42, VERMELHO, "REMOVER ULT");
  desenharBotao(170, 185, 135, 42, AZUL_ESC, "VOLTAR");
}

void desenharTelaCadastrar(String msgStatus) {
  telaAtual = TELA_CADASTRAR;
  tft.fillScreen(FUNDO);
  desenharCabecalho("CADASTRAR ITEM");

  tft.setTextColor(AMARELO, FUNDO);
  tft.setTextSize(2);
  tft.setCursor(15, 52);
  tft.print("Aproxime Tag RFID");
  tft.setCursor(15, 76);
  tft.print("ou leia QR na S3");

  tft.setTextColor(VERDE, FUNDO);
  tft.setTextSize(1);
  tft.setCursor(15, 115);
  tft.print(msgStatus);

  tft.setTextColor(CINZA, FUNDO);
  tft.setCursor(15, 140);
  tft.print("Total em memoria: " + String(totalItens) + "/" + String(MAX_ITENS));

  desenharBotao(170, 185, 135, 42, AZUL_ESC, "VOLTAR");
}

void desenharTelaEmprestimo(String msgStatus) {
  telaAtual = TELA_EMPRESTIMO;
  tft.fillScreen(FUNDO);
  desenharCabecalho("EMPRESTIMO / DEVOL");

  uint16_t corBancada = (modoEmprestimo == EMP_BANCADA) ? VERDE : CINZA;
  uint16_t corCasa    = (modoEmprestimo == EMP_CASA)    ? LARANJA : CINZA;

  desenharBotao(15, 46, 138, 42, corBancada, "BANCADA");
  desenharBotao(167, 46, 138, 42, corCasa, "CASA");

  tft.setTextColor(BRANCO, FUNDO);
  tft.setTextSize(1);
  tft.setCursor(15, 102);
  tft.print("Aproxime o item (NFC ou QR S3) para");
  tft.setCursor(15, 116);
  tft.print("emprestar ou devolver automaticamente:");

  tft.setTextColor(AMARELO, FUNDO);
  tft.setTextSize(1);
  tft.setCursor(15, 145);
  tft.print(msgStatus);

  desenharBotao(170, 185, 135, 42, AZUL_ESC, "VOLTAR");
}

// ===== LOGICA CENTRAL DE MOVIMENTACAO (NFC OU QR S3) =====
void processarCodigoItem(String codigo, String origem) {
  renovarSessao();

  if (telaAtual == TELA_CADASTRAR) {
    if (buscarIndiceItem(codigo) != -1) {
      desenharTelaCadastrar("Item ja cadastrado: " + codigo);
      return;
    }
    if (totalItens < MAX_ITENS) {
      inventario[totalItens] = { codigo, "Item " + origem, DISP, "" };
      totalItens++;
      desenharTelaCadastrar("Cadastrado (" + origem + "): " + codigo);
    } else {
      desenharTelaCadastrar("Memoria cheia!");
    }
  }
  else if (telaAtual == TELA_EMPRESTIMO) {
    int idx = buscarIndiceItem(codigo);
    if (idx == -1) {
      desenharTelaEmprestimo("ERRO: Item nao cadastrado!");
      return;
    }

    if (inventario[idx].status == DISP) {
      inventario[idx].status = modoEmprestimo;
      inventario[idx].responsavel = usuarioLogado;
      String tipoStr = (modoEmprestimo == EMP_BANCADA) ? "BANCADA" : "CASA";
      desenharTelaEmprestimo("EMPRESTADO (" + tipoStr + "): " + codigo);
    } else {
      inventario[idx].status = DISP;
      inventario[idx].responsavel = "";
      desenharTelaEmprestimo("DEVOLVIDO AO LAB: " + codigo);
    }
  }
}

// ===== ENDPOINTS HTTP (INTEGRACAO COM ESP32-S3 CAMERA) =====
void configurarRotasWiFi() {
  server.on("/api/status", HTTP_GET, []() {
    String json = "{\"status\":\"online\",\"tela\":" + String(telaAtual) + ",\"itens\":" + String(totalItens) + "}";
    server.send(200, "application/json", json);
  });

  server.on("/api/qrcode", HTTP_ANY, []() {
    if (!server.hasArg("code")) {
      server.send(400, "application/json", "{\"erro\":\"Parametro 'code' ausente\"}");
      return;
    }
    ultimoCodigoRecebidoS3 = server.arg("code");
    Serial.println("[Wi-Fi S3] QR Code recebido: " + ultimoCodigoRecebidoS3);

    processarCodigoItem(ultimoCodigoRecebidoS3, "QR-S3");

    server.send(200, "application/json", "{\"status\":\"recebido\",\"code\":\"" + ultimoCodigoRecebidoS3 + "\"}");
  });

  server.begin();
}

// ===== LEITURA DO TOUCHSCREEN =====
void processarToque() {
  if (!ts.tirqTouched() || !ts.touched()) return;
  if (millis() - ultimoToque < 300) return;

  TS_Point p = ts.getPoint();
  ultimoToque = millis();

  int x = map(p.x, 200, 3700, 0, 320);
  int y = map(p.y, 240, 3800, 0, 240);
  x = constrain(x, 0, 319);
  y = constrain(y, 0, 239);

  if (telaAtual == TELA_LOGIN) return;
  renovarSessao();

  if (telaAtual == TELA_MENU) {
    if (x >= 15 && x <= 153 && y >= 65 && y <= 130) {
      desenharTelaInventario();
    }
    else if (x >= 167 && x <= 305 && y >= 65 && y <= 130) {
      desenharTelaCadastrar("Aguardando leitura...");
    }
    else if (x >= 15 && x <= 153 && y >= 145 && y <= 210) {
      desenharTelaEmprestimo("Modo: BANCADA. Aguardando item...");
    }
    else if (x >= 167 && x <= 305 && y >= 145 && y <= 210) {
      usuarioLogado = "";
      perfilLogado = "";
      desenharTelaLogin();
    }
  }
  else if (telaAtual == TELA_INVENTARIO) {
    if (x >= 15 && x <= 150 && y >= 185 && y <= 227) {
      if (totalItens > 0) totalItens--;
      desenharTelaInventario();
    }
    else if (x >= 170 && x <= 305 && y >= 185 && y <= 227) {
      desenharTelaMenu();
    }
  }
  else if (telaAtual == TELA_CADASTRAR) {
    if (x >= 170 && x <= 305 && y >= 185 && y <= 227) {
      desenharTelaMenu();
    }
  }
  else if (telaAtual == TELA_EMPRESTIMO) {
    if (x >= 15 && x <= 153 && y >= 46 && y <= 88) {
      modoEmprestimo = EMP_BANCADA;
      desenharTelaEmprestimo("Modo selecionado: BANCADA");
    }
    else if (x >= 167 && x <= 305 && y >= 46 && y <= 88) {
      modoEmprestimo = EMP_CASA;
      desenharTelaEmprestimo("Modo selecionado: CASA");
    }
    else if (x >= 170 && x <= 305 && y >= 185 && y <= 227) {
      desenharTelaMenu();
    }
  }
}

// ===== SETUP =====
void setup() {
  Serial.begin(115200);

  pinMode(TFT_BL, OUTPUT);
  digitalWrite(TFT_BL, HIGH);

  tft.init();
  tft.setRotation(1);

  touchSPI.begin(XPT2046_CLK, XPT2046_MISO, XPT2046_MOSI, XPT2046_CS);
  ts.begin(touchSPI);
  ts.setRotation(1);

  I2CNFC.begin(NFC_SDA, NFC_SCL, 100000);
  nfc.begin();
  if (nfc.getFirmwareVersion() != 0) {
    nfc.SAMConfig();
    nfcOK = true;
  }

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  unsigned long tWifi = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - tWifi < 8000) {
    delay(250);
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("Wi-Fi conectado! IP: " + WiFi.localIP().toString());
    configurarRotasWiFi();
  }

  desenharTelaLogin();
}

// ===== LOOP PRINCIPAL =====
void loop() {
  if (WiFi.status() == WL_CONNECTED) {
    server.handleClient();
  }

  if (telaAtual != TELA_LOGIN && (millis() - inicioSessao > SESSAO_TTL_MS)) {
    usuarioLogado = "";
    perfilLogado = "";
    desenharTelaLogin();
  }

  processarToque();

  if (nfcOK) {
    uint8_t uid[7];
    uint8_t tamanhoUID = 0;
    if (nfc.readPassiveTargetID(PN532_MIFARE_ISO14443A, uid, &tamanhoUID, 60)) {
      String uidTexto = formatarUID(uid, tamanhoUID);

      if (telaAtual == TELA_LOGIN) {
        int idxUser = buscarIndiceUsuario(uid, tamanhoUID);
        if (idxUser != -1) {
          usuarioLogado = String(usuariosAutorizados[idxUser].nome);
          perfilLogado  = String(usuariosAutorizados[idxUser].perfil);
          mostrarBoasVindasPerfil(usuarioLogado, perfilLogado);
          renovarSessao();
          desenharTelaMenu();
        } else {
          tft.fillRoundRect(15, 165, 290, 35, 6, VERMELHO);
          tft.setTextColor(BRANCO, VERMELHO);
          tft.setTextSize(2);
          tft.setCursor(45, 174);
          tft.print("CRACHA NAO AUTORIZADO");
          delay(1500);
          desenharTelaLogin();
        }
      }
      else if (telaAtual == TELA_CADASTRAR || telaAtual == TELA_EMPRESTIMO) {
        processarCodigoItem(uidTexto, "NFC");
        delay(1000);
      }
    }
  }
}