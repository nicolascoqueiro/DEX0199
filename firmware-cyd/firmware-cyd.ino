#include <Wire.h>
#include <TFT_eSPI.h>
#include <Adafruit_PN532.h>

// Controle de Backlight na placa CYD (ESP32-2432S028)
#define TFT_BL 21

// ===== DISPLAY =====
TFT_eSPI tft = TFT_eSPI();

// ===== NFC: ELECHOUSE PN532 V3 EM I2C =====
#define NFC_SDA 27
#define NFC_SCL 22

TwoWire I2CNFC = TwoWire(1);
Adafruit_PN532 nfc(-1, -1, &I2CNFC);

// ===== CARTOES AUTORIZADOS =====
const uint8_t cartao1[] = { 0x4D, 0x87, 0x4E, 0x07 };
const uint8_t cartao2[] = { 0xC0, 0x3E, 0x35, 0x5C };

// ===== CORES (RGB565) =====
#define FUNDO    0x10A2
#define AZUL     0x2D7F
#define BRANCO   0xFFFF
#define VERDE    0x07E0
#define VERMELHO 0xF800
#define AMARELO  0xFFE0
#define CINZA    0xC618

String ultimoUID = "";
unsigned long ultimaLeitura = 0;
bool nfcOK = false;

// ===== FORMATAR UID =====
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

// ===== VERIFICAR AUTORIZACAO =====
bool estaAutorizado(uint8_t *uid, uint8_t tamanho) {
  if (tamanho != 4) return false;
  bool c1 = memcmp(uid, cartao1, 4) == 0;
  bool c2 = memcmp(uid, cartao2, 4) == 0;
  return (c1 || c2);
}

// ===== TELA INICIAL =====
void desenharTelaInicial() {
  tft.fillScreen(FUNDO);

  tft.fillRect(0, 0, 320, 48, AZUL);
  tft.setTextColor(BRANCO, AZUL);
  tft.setTextSize(2);
  tft.setCursor(18, 15);
  tft.print("CONTROLE NFC");

  tft.drawRoundRect(15, 65, 290, 115, BRANCO, 10);

  tft.setTextColor(AMARELO, FUNDO);
  tft.setCursor(35, 88);
  tft.print("APROXIME O");

  tft.setCursor(35, 115);
  tft.print("SEU CARTAO");

  tft.setTextColor(CINZA, FUNDO);
  tft.setTextSize(1);
  tft.setCursor(20, 205);
  tft.print("Leitor: Elechouse PN532 V3");

  tft.drawFastHLine(15, 230, 290, CINZA);
  tft.setCursor(20, 245);
  tft.print("NFC pronto - aguardando...");
}

// ===== TELA DE CARTAO =====
void mostrarCartao(String uid, bool autorizado) {
  tft.fillScreen(FUNDO);

  tft.fillRect(0, 0, 320, 48, AZUL);
  tft.setTextColor(BRANCO, AZUL);
  tft.setTextSize(2);
  tft.setCursor(18, 15);
  tft.print("CARTAO IDENTIFICADO");

  tft.setTextColor(BRANCO, FUNDO);
  tft.setTextSize(2);
  tft.setCursor(18, 70);
  tft.print("UID:");

  tft.setTextSize(2);
  tft.setCursor(18, 102);

  if (uid.length() > 18) {
    tft.setTextSize(1);
    tft.print(uid.substring(0, 18));
    tft.setCursor(18, 122);
    tft.print(uid.substring(18));
  } else {
    tft.print(uid);
  }

  if (autorizado) {
    tft.fillRoundRect(15, 155, 290, 60, VERDE, 10);
    tft.setTextColor(BRANCO, VERDE);
    tft.setTextSize(2);
    tft.setCursor(35, 177);
    tft.print("ACESSO PERMITIDO");
  } else {
    tft.fillRoundRect(15, 155, 290, 60, VERMELHO, 10);
    tft.setTextColor(BRANCO, VERMELHO);
    tft.setTextSize(2);
    tft.setCursor(35, 177);
    tft.print("ACESSO NEGADO");
  }

  tft.setTextColor(CINZA, FUNDO);
  tft.setTextSize(1);
  tft.setCursor(20, 245);
  tft.print("Retire o cartao para continuar");
}

// ===== INICIALIZACAO =====
void setup() {
  Serial.begin(115200);
  delay(1000);

  // Liga luz de fundo da tela na CYD
  pinMode(TFT_BL, OUTPUT);
  digitalWrite(TFT_BL, HIGH);

  // Inicializa display
  tft.init();
  tft.setRotation(1);
  desenharTelaInicial();

  Serial.println();
  Serial.println("CONTROLE NFC - ESP32-2432S028");

  // Barramento I2C dedicado ao PN532
  I2CNFC.begin(NFC_SDA, NFC_SCL, 100000);
  delay(100);

  Serial.println("Iniciando PN532...");
  nfc.begin();

  Serial.println("Consultando firmware...");
  uint32_t versao = nfc.getFirmwareVersion();

  if (versao == 0) {
    nfcOK = false;
    Serial.println("ERRO: PN532 nao encontrado!");

    tft.fillScreen(FUNDO);
    tft.setTextColor(VERMELHO, FUNDO);
    tft.setTextSize(2);
    tft.setCursor(15, 65);
    tft.println("ERRO NFC");

    tft.setTextColor(BRANCO, FUNDO);
    tft.setTextSize(1);
    tft.setCursor(15, 105);
    tft.println("PN532 nao respondeu.");
    tft.setCursor(15, 125);
    tft.println("Confira modo I2C.");
    return;
  }

  Serial.printf("Firmware: 0x%08lX\n", (unsigned long)versao);
  nfc.SAMConfig();
  nfcOK = true;

  Serial.println("PN532 pronto. Aproxime um cartao.");
  desenharTelaInicial();
}

// ===== LEITURA DOS CARTOES =====
void loop() {
  if (!nfcOK) {
    delay(1000);
    return;
  }

  uint8_t uid[7];
  uint8_t tamanhoUID = 0;

  bool encontrado = nfc.readPassiveTargetID(
    PN532_MIFARE_ISO14443A,
    uid,
    &tamanhoUID,
    500
  );

  if (encontrado) {
    String uidTexto = formatarUID(uid, tamanhoUID);

    if (uidTexto != ultimoUID || millis() - ultimaLeitura > 2500) {
      ultimoUID = uidTexto;
      ultimaLeitura = millis();

      bool autorizado = estaAutorizado(uid, tamanhoUID);

      Serial.print("UID: ");
      Serial.println(uidTexto);
      Serial.println(autorizado ? "ACESSO PERMITIDO" : "ACESSO NEGADO");

      mostrarCartao(uidTexto, autorizado);
    }
  } else {
    if (ultimoUID != "" && millis() - ultimaLeitura > 4000) {
      ultimoUID = "";
      desenharTelaInicial();
    }
  }

  delay(50);
}