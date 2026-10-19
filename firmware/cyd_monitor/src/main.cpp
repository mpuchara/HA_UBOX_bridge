#include <Arduino.h>
#include <WiFi.h>
#include <WiFiClient.h>
#include <HTTPClient.h>
#include <TFT_eSPI.h>
#include <TJpg_Decoder.h>
#include <memory>
#include "config.h"

// ESP32-2432S028 (classic 2.8" Cheap Yellow Display / ILI9341).
// Alternate CYD board revisions can have different pinouts.
static constexpr int TFT_BACKLIGHT_PIN = 21;
static constexpr size_t MAX_JPEG_BYTES = 100 * 1024;
TFT_eSPI tft;
String lastEtag;
unsigned long lastPoll = 0;
unsigned long lastWifiTry = 0;

bool tftBlock(int16_t x, int16_t y, uint16_t w, uint16_t h, uint16_t* colors) {
  if (y >= tft.height() || x >= tft.width()) return false;
  tft.pushImage(x, y, w, h, colors);
  return true;
}
void showStatus(const char* message, uint16_t color = TFT_WHITE) {
  // Only show the status bar until the first successful image; retain cached
  // JPEG on network problems instead of blanking the screen.
  if (lastEtag.length()) {
    Serial.println(message);
    return;
  }
  tft.fillRect(0, 0, tft.width(), 22, TFT_BLACK);
  tft.setTextColor(color, TFT_BLACK);
  tft.drawString(message, 6, 5, 2);
  Serial.println(message);
}
void reconnectIfNeeded() {
  if (WiFi.status() == WL_CONNECTED) return;
  if (lastWifiTry != 0 && millis() - lastWifiTry < 10000) return;
  lastWifiTry = millis();
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  showStatus("Laczenie z Wi-Fi...", TFT_YELLOW);
}

void pollImage() {
  if (WiFi.status() != WL_CONNECTED) {
    showStatus("Brak Wi-Fi", TFT_YELLOW);
    return;
  }
  WiFiClient client;
  HTTPClient http;
  const String url = String("http://") + HA_IP_ADDRESS + ":8100/snapshot.jpg";
  if (!http.begin(client, url)) {
    showStatus("Nie mozna polaczyc z HA", TFT_RED);
    return;
  }
  http.setTimeout(7000);
  http.setReuse(false);
  const char* responseHeaders[] = {"ETag"};
  http.collectHeaders(responseHeaders, 1);
  http.addHeader("X-UBox-Token", UBOX_SNAPSHOT_TOKEN);
  if (lastEtag.length()) http.addHeader("If-None-Match", lastEtag);

  int status = http.GET();
  if (status == HTTP_CODE_NOT_MODIFIED) {
    // No downloaded JPEG bytes; image already displayed is still current.
    http.end();
    return;
  }
  if (status != HTTP_CODE_OK) {
    Serial.printf("Snapshot HTTP status: %d\n", status);
    showStatus(status == 401 ? "Token CYD jest niepoprawny" : "Czekam na zdjecie...", TFT_YELLOW);
    http.end();
    return;
  }

  const int count = http.getSize();
  if (count < 4 || count > static_cast<int>(MAX_JPEG_BYTES)) {
    showStatus("Niepoprawny rozmiar JPEG", TFT_RED);
    http.end();
    return;
  }
  std::unique_ptr<uint8_t[]> bytes(new (std::nothrow) uint8_t[count]);
  if (!bytes) {
    showStatus("Za malo pamieci na JPEG", TFT_RED);
    http.end();
    return;
  }
  auto* stream = http.getStreamPtr();
  stream->setTimeout(7);
  const size_t received = stream->readBytes(bytes.get(), count);
  if (received != static_cast<size_t>(count)) {
    showStatus("Przerwane pobieranie", TFT_RED);
    http.end();
    return;
  }
  const String etag = http.header("ETag");
  const JRESULT error = TJpgDec.drawJpg(0, 0, bytes.get(), static_cast<uint32_t>(received));
  if (error == JDR_OK) {
    lastEtag = etag;
    Serial.printf("Nowy obraz: %u bajtow, ETag %s\n", static_cast<unsigned>(received), etag.c_str());
  } else {
    showStatus("Nie mozna dekodowac JPEG", TFT_RED);
    Serial.printf("JPEG decoder error: %d\n", static_cast<int>(error));
  }
  http.end();
}
void setup() {
  Serial.begin(115200);
  pinMode(TFT_BACKLIGHT_PIN, OUTPUT);
  digitalWrite(TFT_BACKLIGHT_PIN, HIGH);
  tft.init();
  tft.setRotation(1);  // 320x240
  tft.fillScreen(TFT_BLACK);
  TJpgDec.setJpgScale(1);
  TJpgDec.setSwapBytes(true);
  TJpgDec.setCallback(tftBlock);
  showStatus("UBox Bridge - start");
  reconnectIfNeeded();
}
void loop() {
  reconnectIfNeeded();
  if (lastPoll == 0 || millis() - lastPoll >= CYD_REFRESH_MS) {
    lastPoll = millis();
    pollImage();
  }
  delay(100);
}
