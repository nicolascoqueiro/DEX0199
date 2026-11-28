#define USER_SETUP_INFO "CYD_ESP32_2432S028"

// Compatibilidade com arduino-esp32 >= 4.0 (ESP-IDF 6 removeu VSPI_HOST/HSPI_HOST)
#if defined(ESP_ARDUINO_VERSION_MAJOR) && (ESP_ARDUINO_VERSION_MAJOR >= 4)
  #ifndef VSPI_HOST
    #define VSPI_HOST SPI3_HOST
  #endif
  #ifndef HSPI_HOST
    #define HSPI_HOST SPI2_HOST
  #endif
#endif

// Use o driver _2 para corrigir a orientacao da CYD
#define ILI9341_2_DRIVER

#define TFT_WIDTH  240
#define TFT_HEIGHT 320

#define TFT_MISO 12
#define TFT_MOSI 13
#define TFT_SCLK 14
#define TFT_CS   15
#define TFT_DC    2
#define TFT_RST  -1
#define TFT_BL   21

#define TFT_BACKLIGHT_ON HIGH

#define LOAD_GLCD
#define LOAD_FONT2
#define LOAD_FONT4
#define LOAD_FONT6
#define LOAD_FONT7
#define LOAD_FONT8
#define LOAD_GFXFF
#define SMOOTH_FONT

#define SPI_FREQUENCY       40000000
#define SPI_READ_FREQUENCY  20000000
#define SPI_TOUCH_FREQUENCY  2500000