#include <Arduino.h>
#include <WiFi.h>
#include <WiFiClient.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include <WiFiManager.h>
#include <TFT_eSPI.h>
#include <TJpg_Decoder.h>
#include <esp_system.h>
#include <memory>
#include <new>

// CYD ESP32-2432S028 (ILI9341, 2.8", 320x240).
// Configuration is stored in ESP32 NVS, NEVER compiled into the firmware.
static constexpr int TFT_BACKLIGHT_PIN = 21;
static constexpr int BOOT_BUTTON_PIN = 0;
static constexpr unsigned long REFRESH_MS = 30000UL;
static constexpr size_t MAX_JPEG_BYTES = 100 * 1024;

TFT_eSPI tft;
String haHost;
String snapshotToken;
String lastEtag;
unsigned long lastPoll = 0;
unsigned long lastReconnect = 0;
unsigned long bootHeldFrom = 0;
bool buttonResetTriggered = false;

bool tftBlock(int16_t x, int16_t y, uint16_t w, uint16_t h, uint16_t* colors) {
  if (x >= tft.width() || y >= tft.height()) return false;
  tft.pushImage(x, y, w, h, colors);
  return true;
}

void writeScreenLine(const String& line, int y, uint16_t color = TFT_WHITE) {
  tft.setTextColor(color, TFT_BLACK);
  tft.drawString(line, 8, y, 2);
}

void showMessage(const String& message, uint16_t color = TFT_WHITE) {
  Serial.println(message);
  // Avoid erasing the previously received image on transient failures.
  if (!lastEtag.isEmpty()) return;
  tft.fillRect(0, 0, tft.width(), 36, TFT_BLACK);
  writeScreenLine(message, 4, color);
}

void loadSettings() {
  Preferences prefs;
  if (!prefs.begin("ubox-cyd", true)) return;
  haHost = prefs.getString("ha_host", "");
  snapshotToken = prefs.getString("token", "");
  prefs.end();
  haHost.trim();
  snapshotToken.trim();
}

void persistSettings(const String& host, const String& token) {
  Preferences prefs;
  if (!prefs.begin("ubox-cyd", false)) return;
  prefs.putString("ha_host", host);
  prefs.putString("token", token);
  prefs.end();
}

void configPortalScreen(const String& apName, const String& apPassword) {
  tft.fillScreen(TFT_BLACK);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.drawString("UBox CYD - konfiguracja", 8, 8, 2);
  writeScreenLine("1. Polacz sie z Wi-Fi:", 8+34);
  writeScreenLine(apName, 10+60, TFT_CYAN);
  writeScreenLine("Haslo:", 10+94);
  writeScreenLine(apPassword, 10+118, TFT_GREEN);
  writeScreenLine("2. Otworz w przegladarce:", 10+148);
  writeScreenLine("http://192.168.4.1", 10+174, TFT_CYAN);
  writeScreenLine("3. Ustaw Wi-Fi, IP HA i token", 10+201);
}

bool configureNetworking(bool forcePortal) {
  char hostBuffer[100] = {};
  char tokenBuffer[100] = {};
  haHost.toCharArray(hostBuffer, sizeof(hostBuffer));
  snapshotToken.toCharArray(tokenBuffer, sizeof(tokenBuffer));

  WiFiManager wifiManager;
  WiFiManagerParameter hostParam("ha_host", "Adres IP Raspberry Pi (bez http i :8123)", hostBuffer, sizeof(hostBuffer));
  WiFiManagerParameter tokenParam("ubox_token", "Token UBox Bridge", tokenBuffer, sizeof(tokenBuffer), "type=\"password\"");
  wifiManager.addParameter(&hostParam);
  wifiManager.addParameter(&tokenParam);
  wifiManager.setConnectTimeout(20);
  wifiManager.setConfigPortalTimeout(0); // Wait until user finishes provisioning.
  wifiManager.setTitle("UBox CYD - ustawienia");

  // Random WPA2 AP password is shown only on the physical display.
  const uint32_t nonce = esp_random();
  const String apName = "UBox-CYD-" + String(nonce & 0xffff, HEX);
  const String apPassword = "ucyd" + String(nonce, HEX) + "!";
  // 4 + (up to 8) + 1 chars, always >= 8 bytes.
  bool connected = false;
  if (forcePortal || haHost.isEmpty() || snapshotToken.isEmpty()) {
    configPortalScreen(apName, apPassword);
    connected = wifiManager.startConfigPortal(apName.c_str(), apPassword.c_str());
  } else {
    showMessage("Laczenie Wi-Fi...", TFT_YELLOW);
    // On failure WiFiManager creates an AP with the same credentials.
    // The callback is not guaranteed to fire before we render the AP info,
    // so a manual reset (BOOT hold) will always force reconfiguration.
    connected = wifiManager.autoConnect(apName.c_str(), apPassword.c_str());
  }
  if (!connected) {
    showMessage("Nie polaczono z Wi-Fi", TFT_RED);
    return false;
  }

  String newHost(hostParam.getValue());
  String newToken(tokenParam.getValue());
  newHost.trim();
  newToken.trim();
  // Only host/IP is accepted, never an arbitrary URL/path.
  if (newHost.startsWith("http://")) newHost.remove(0, 7);
  if (newHost.startsWith("https://")) newHost.remove(0, 8);
  int slash = newHost.indexOf('/');
  if (slash >= 0) newHost = newHost.substring(0, slash);
  int colon = newHost.indexOf(':');
  if (colon >= 0) newHost = newHost.substring(0, colon);
  if (newHost.length() > 0 && newHost.length() < 100) haHost = newHost;
  if (newToken.length() > 0 && newToken.length() < 100) snapshotToken = newToken;
  if (haHost.isEmpty() || snapshotToken.isEmpty()) {
    showMessage("Brak IP HA lub tokenu", TFT_RED);
    return false;
  }
  persistSettings(haHost, snapshotToken);
  Serial.printf("Wi-Fi connected; CYD IP: %s\n", WiFi.localIP().toString().c_str());
  return true;
}

void resetProvisioning() {
  showMessage("Reset ustawien...", TFT_YELLOW);
  Preferences prefs;
  if (prefs.begin("ubox-cyd", false)) {
    prefs.clear();
    prefs.end();
  }
  WiFiManager manager;
  manager.resetSettings();
  delay(300);
  ESP.restart();
}

void pollImage() {
  if (WiFi.status() != WL_CONNECTED) {
    showMessage("Czekam na Wi-Fi", TFT_YELLOW);
    return;
  }
  if (haHost.isEmpty() || snapshotToken.isEmpty()) {
    showMessage("Brak konfiguracji HA", TFT_RED);
    return;
  }
  WiFiClient client;
  HTTPClient http;
  const String url = "http://" + haHost + ":8100/snapshot.jpg";
  if (!http.begin(client, url)) {
    showMessage("Blad polaczenia HA", TFT_RED);
    return;
  }
  http.setTimeout(7000);
  http.setReuse(false);
  const char* headers[] = {"ETag"};
  http.collectHeaders(headers, 1);
  http.addHeader("X-UBox-Token", snapshotToken);
  if (!lastEtag.isEmpty()) http.addHeader("If-None-Match", lastEtag);

  const int status = http.GET();
  if (status == HTTP_CODE_NOT_MODIFIED) {
    http.end();
    return;
  }
  if (status != HTTP_CODE_OK) {
    Serial.printf("HA snapshot HTTP: %d\n", status);
    if (status == 401) showMessage("Niepoprawny token", TFT_RED);
    else showMessage("Czekam na obraz...", TFT_YELLOW);
    http.end();
    return;
  }
  const int count = http.getSize();
  if (count < 4 || count > static_cast<int>(MAX_JPEG_BYTES)) {
    showMessage("JPEG za duzy / brak danych", TFT_RED);
    http.end();
    return;
  }
  std::unique_ptr<uint8_t[]> bytes(new (std::nothrow) uint8_t[count]);
  if (!bytes) {
    showMessage("Brak pamieci RAM", TFT_RED);
    http.end();
    return;
  }
  auto* stream = http.getStreamPtr();
  stream->setTimeout(7000);
  const size_t received = stream->readBytes(bytes.get(), count);
  if (received != static_cast<size_t>(count)) {
    showMessage("Niepelny obraz", TFT_RED);
    http.end();
    return;
  }
  const String etag = http.header("ETag");
  const JRESULT result = TJpgDec.drawJpg(0, 0, bytes.get(), static_cast<uint32_t>(received));
  if (result == JDR_OK) {
    lastEtag = etag;
    Serial.printf("New JPEG: %u bytes\n", static_cast<unsigned>(received));
  } else {
    Serial.printf("JPEG error: %d\n", static_cast<int>(result));
    showMessage("Blad dekodowania JPEG", TFT_RED);
  }
  http.end();
}

void setup() {
  Serial.begin(115200);
  pinMode(BOOT_BUTTON_PIN, INPUT_PULLUP);
  pinMode(TFT_BACKLIGHT_PIN, OUTPUT);
  digitalWrite(TFT_BACKLIGHT_PIN, HIGH);
  tft.init();
  tft.setRotation(1); // 320x240 landscape
  tft.fillScreen(TFT_BLACK);
  TJpgDec.setJpgScale(1);
  TJpgDec.setSwapBytes(true);
  TJpgDec.setCallback(tftBlock);
  writeScreenLine("UBox CYD - start...", 8);
  loadSettings();
  configureNetworking(false);
}

void loop() {
  // Hold BOOT for 5s AFTER booting (not during reset) to reconfigure.
  // Pressing BOOT during reset instead enters ESP32 flashing mode.
  if (digitalRead(BOOT_BUTTON_PIN) == LOW) {
    if (!bootHeldFrom) bootHeldFrom = millis();
    if (!buttonResetTriggered && millis() - bootHeldFrom >= 5000) {
      buttonResetTriggered = true;
      resetProvisioning();
    }
  } else {
    bootHeldFrom = 0;
  }
  if (WiFi.status() != WL_CONNECTED) {
    if (millis() - lastReconnect > 10000) {
      lastReconnect = millis();
      WiFi.reconnect();
    }
  }
  if (lastPoll == 0 || millis() - lastPoll >= REFRESH_MS) {
    lastPoll = millis();
    pollImage();
  }
  delay(100);
}
