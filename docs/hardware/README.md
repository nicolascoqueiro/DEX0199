# Hardware e Pinagem

O sistema é composto por dois nós embarcados conectados à mesma rede Wi-Fi do servidor local:

1. **Terminal Principal / Kiosk (`ESP32-2432S028` - Cheap Yellow Display):**
   - Display TFT 2.8" `ILI9341` + Touch resistivo `XPT2046` (SPI dedicado);
   - Leitor NFC/RFID `Elechouse PN532 V3 Red` via I2C no conector `CN1` (`SDA=IO27`, `SCL=IO22`);
   - Módulo RTC `DS3231SN` (opcional) compartilhando o mesmo barramento I2C (`0x68`).
   - Detalhes completos em [firmware-cyd/README.md](../../firmware-cyd/README.md).

2. **Estação Óptica (`ESP32-S3` com Câmera OV2640):**
   - Captura frames QVGA em escala de cinza e decodifica QR Codes localmente com `quirc`;
   - Suporte configurável em `firmware-s3/config.h` para `ESP32S3_EYE` / `Freenove ESP32-S3-WROOM CAM`, `XIAO ESP32S3 Sense` e `ESP32S3_CAM_LCD`.
   - Detalhes completos em [firmware-s3/README.md](../../firmware-s3/README.md).
