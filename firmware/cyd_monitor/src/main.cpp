#include <Arduino.h>
#include <WiFi.h>
#include <WiFiClient.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include <WiFiManager.h>
#include <TFT_eSPI.h>
#include <TJpg_Decoder.h>
#include <SPI.h>
#include <XPT2046_Touchscreen.h>
#include <ArduinoJson.h>
#include <math.h>
#include <esp_system.h>
#include <memory>
#include <new>

// CYD ESP32-2432S028 (ILI9341, 2.8", landscape 320x240).
// Configuration is stored in ESP32 NVS, NEVER compiled into the firmware.
// TFT_BL is provided per board build: dual-USB ST7789 may use GPIO27;
// other ST7789 / ILI9341 variants often use GPIO21.
static constexpr int TFT_BACKLIGHT_PIN = TFT_BL;
static constexpr int LDR_ADC_PIN = 34;
static constexpr int BOOT_BUTTON_PIN = 0;
static constexpr unsigned long REFRESH_MS = 30000UL;
static constexpr unsigned long PTZ_POLL_MS=2500UL;
static constexpr unsigned long LDR_SAMPLE_MS=2500UL;
static constexpr unsigned long BRIGHTNESS_SYNC_MS=10000UL;
static constexpr unsigned long PTZ_REFRESH_TIMEOUT_MS=110000UL;
static constexpr size_t MAX_JPEG_BYTES = 100 * 1024;
static constexpr uint8_t DEFAULT_SCREEN_ROTATION = 3; // LCD upright with USB lower-right when board is turned clockwise

TFT_eSPI tft;
String haHost;
String snapshotToken;
String lastEtag;
unsigned long lastPoll = 0;
unsigned long lastReconnect = 0;
unsigned long bootHeldFrom = 0;
bool buttonResetTriggered = false;
uint8_t screenRotation = DEFAULT_SCREEN_ROTATION;
// Touch XPT2046 on separate HSPI from display (pins 25/39/32/33/36).
SPIClass touchSPI(HSPI);
XPT2046_Touchscreen touch(33,36);
bool touchReady=false,touchCalibrated=false,touching=false,waitingForPtzImage=false;
float tA=0,tB=0,tC=0,tD=0,tE=0,tF=0;
uint8_t touchCalRotation=DEFAULT_SCREEN_ROTATION;
int16_t dragStartX=0,dragStartY=0,dragCurrentX=0,dragCurrentY=0;
unsigned long dragStartMs=0,gestureNextAllowed=0,ptzImageDeadline=0;
// The board may have an inverted LDR divider. No polarity assumption:
// interpolate between measured night/day ADC anchors, saved by HA panel.
struct BrightnessAnchor { int raw=-1; int percent=100; };
BrightnessAnchor lightNight, lightDay;
bool brightnessCalibrated=false;
bool backlightPwmReady=false;
bool brightnessConfigSeen=false; // Prevent NVS calibration dimming unconfigured screen.
float filteredLdr=0.0f;
bool ldrValid=false;
float currentBrightness=100.0f;
int previewPercent=-1;
unsigned long previewUntil=0, lastLightSample=0, lastBrightnessSync=0, lastBrightnessTelemetry=0;



// HA add-on v0.5.5+ provides landscape 320x240 JPEG, orientation
// adjusted by the ILI9341's hardware rotation (MADCTL), not MCU remapping.
static constexpr uint16_t JPEG_WIDTH = 320;
static constexpr uint16_t JPEG_HEIGHT = 240;
static bool jpegGeometryError = false;
static uint32_t jpegPixelsWritten = 0;

bool tftBlock(int16_t x, int16_t y, uint16_t w, uint16_t h, uint16_t* colors) {
  if (!colors || x < 0 || y < 0 || !w || !h ||
      static_cast<uint32_t>(x) + w > tft.width() ||
      static_cast<uint32_t>(y) + h > tft.height()) {
    jpegGeometryError = true;
    return false;
  }
  tft.pushImage(x, y, w, h, colors);
  jpegPixelsWritten += static_cast<uint32_t>(w) * h;
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
  screenRotation = prefs.getUChar("screen_rot", DEFAULT_SCREEN_ROTATION);
  if (screenRotation != 1 && screenRotation != 3) screenRotation = DEFAULT_SCREEN_ROTATION;
  prefs.end();
  haHost.trim();
  snapshotToken.trim();
}

void saveRotation(uint8_t rotation) {
  Preferences prefs;
  if (!prefs.begin("ubox-cyd", false)) return;
  prefs.putUChar("screen_rot", rotation);
  prefs.end();
}

void loadTouchCalibration(){
  Preferences prefs;
  if(!prefs.begin("ubox-cyd",true))return;
  touchCalibrated=prefs.getBool("tc_ok",false);
  touchCalRotation=prefs.getUChar("tc_rot",DEFAULT_SCREEN_ROTATION);
  tA=prefs.getFloat("tc_a",0);tB=prefs.getFloat("tc_b",0);
  tC=prefs.getFloat("tc_c",0);tD=prefs.getFloat("tc_d",0);
  tE=prefs.getFloat("tc_e",0);tF=prefs.getFloat("tc_f",0);
  prefs.end();
  if(!isfinite(tA)||!isfinite(tB)||!isfinite(tC)||!isfinite(tD)||!isfinite(tE)||!isfinite(tF))
    touchCalibrated=false;
}
bool readTouchXY(int16_t& x,int16_t& y){
  if(!touchReady||!touchCalibrated||!touch.touched())return false;
  const TS_Point p=touch.getPoint();
  float xf=tA*p.x+tB*p.y+tC;
  float yf=tD*p.x+tE*p.y+tF;
  if(screenRotation!=touchCalRotation){xf=319-xf;yf=239-yf;}
  if(!isfinite(xf)||!isfinite(yf)||xf < -16||xf > 335||yf < -16||yf > 255)return false;
  x=constrain(int(roundf(xf)),0,319);y=constrain(int(roundf(yf)),0,239);
  return true;
}
bool calibrateTarget(int16_t sx,int16_t sy,int16_t& rx,int16_t& ry,int index){
  tft.fillScreen(TFT_BLACK);
  writeScreenLine("DOTYK: kalibracja "+String(index)+"/3",8);
  writeScreenLine("Dotknij znaku +",37,TFT_YELLOW);
  tft.drawFastHLine(sx-13,sy,27,TFT_YELLOW);
  tft.drawFastVLine(sx,sy-13,27,TFT_YELLOW);
  const unsigned long beginAt=millis();
  while(millis()-beginAt < 14000UL){
    if(touch.touched()){
      int32_t sumx=0,sumy=0;int count=0;
      const unsigned long started=millis();
      while(touch.touched()&&millis()-started < 650UL){
        const TS_Point pt=touch.getPoint();
        if(pt.z>100){sumx+=pt.x;sumy+=pt.y;count++;}
        delay(25);
      }
      while(touch.touched()&&millis()-started < 1500UL)delay(25);
      if(count>=2){rx=sumx/count;ry=sumy/count;return true;}
    }
    delay(30);
  }
  return false;
}
bool calibrateTouch(){
  if(!touchReady)return false;
  const int16_t sx[3]={25,295,25},sy[3]={65,65,210};
  int16_t rx[3],ry[3];
  for(int i=0;i<3;++i){
    if(!calibrateTarget(sx[i],sy[i],rx[i],ry[i],i+1)){
      tft.fillScreen(TFT_BLACK);
      writeScreenLine("Kalibracja anulowana",10,TFT_YELLOW);
      delay(650);return false;
    }
  }
  const float ux=rx[1]-rx[0],uy=ry[1]-ry[0];
  const float vx=rx[2]-rx[0],vy=ry[2]-ry[0];
  const float det=ux*vy-uy*vx;
  if(fabsf(det)<80000){writeScreenLine("Blad kalibracji",12,TFT_RED);return false;}
  tA=270.0f*vy/det;tB=-270.0f*vx/det;
  tD=-145.0f*uy/det;tE=145.0f*ux/det;
  tC=25.0f-tA*rx[0]-tB*ry[0];tF=65.0f-tD*rx[0]-tE*ry[0];
  touchCalRotation=screenRotation;touchCalibrated=true;
  Preferences prefs;
  if(prefs.begin("ubox-cyd",false)){
    prefs.putBool("tc_ok",true);prefs.putUChar("tc_rot",screenRotation);
    prefs.putFloat("tc_a",tA);prefs.putFloat("tc_b",tB);
    prefs.putFloat("tc_c",tC);prefs.putFloat("tc_d",tD);
    prefs.putFloat("tc_e",tE);prefs.putFloat("tc_f",tF);
    prefs.end();
  }
  tft.fillScreen(TFT_BLACK);
  writeScreenLine("Kalibracja gotowa!",8,TFT_GREEN);
  delay(700);tft.fillScreen(TFT_BLACK);touching=false;
  return true;
}

void persistSettings(const String& host, const String& token) {
  Preferences prefs;
  if (!prefs.begin("ubox-cyd", false)) return;
  prefs.putString("ha_host", host);
  prefs.putString("token", token);
  prefs.end();
}

void displaySelfTest() {
  // Diagnostic, independent of UBox/JPEG. Any noisy/static band in this
  // test is a TFT driver/SPI/power/hardware issue, not a camera issue.
  const int16_t w = tft.width(), h = tft.height();
  tft.fillRect(0, 0, w / 2, h / 2, TFT_RED);
  tft.fillRect(w / 2, 0, w - w / 2, h / 2, TFT_GREEN);
  tft.fillRect(0, h / 2, w / 2, h - h / 2, TFT_BLUE);
  tft.fillRect(w / 2, h / 2, w - w / 2, h - h / 2, TFT_WHITE);
  tft.drawRect(0, 0, w, h, TFT_YELLOW);
  tft.setTextColor(TFT_BLACK, TFT_WHITE);
  tft.drawString("ROT " + String(screenRotation), w / 2 + 12, h / 2 + 12, 2);
  tft.drawString("BL GPIO" + String(TFT_BACKLIGHT_PIN), w / 2 + 8, h / 2 + 62, 2);
#if defined(ST7789_DRIVER)
  tft.setTextColor(TFT_BLACK, TFT_WHITE);
  tft.drawString("ST7789", w / 2 + 8, h / 2 + 38, 2);
#elif defined(ILI9341_DRIVER)
  tft.setTextColor(TFT_BLACK, TFT_WHITE);
  tft.drawString("ILI9341", w / 2 + 8, h / 2 + 38, 2);
#endif
  delay(1600);
  tft.fillScreen(TFT_BLACK);
}

void configPortalScreen(const String& apName, const String& apPassword) {
  tft.fillScreen(TFT_BLACK);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.drawString("CYD - ustawienia", 8, 8, 2);
  writeScreenLine("1. Polacz sie z Wi-Fi:", 8+34);
  writeScreenLine(apName, 10+60, TFT_CYAN);
  writeScreenLine("Haslo:", 10+94);
  writeScreenLine(apPassword, 10+118, TFT_GREEN);
  writeScreenLine("2. Otworz w przegladarce:", 10+148);
  writeScreenLine("http://192.168.4.1", 10+174, TFT_CYAN);
  writeScreenLine("3. Ustaw Wi-Fi, IP HA", 10+201);
  writeScreenLine("i token UBox", 10+221);
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

  // User-requested simple WPA2 password. This is NOT a high-security choice:
  // enable the provisioning AP only briefly and never expose camera credentials
  // to others connected to this AP during setup.
  const String apName = "CYD";
  const String apPassword = "12345678";
  wifiManager.setAPCallback([&](WiFiManager*) {
    configPortalScreen(apName, apPassword);
  });
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
  const String url = "http://" + haHost + ":8100/snapshot-cyd-wide.jpg";
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
  // Avoid drawing an unexpected image geometry into an incorrectly rotated
  // screen; this also prevents stale pixels and apparent horizontal seams.
  uint16_t jpgWidth = 0, jpgHeight = 0;
  if (TJpgDec.getJpgSize(&jpgWidth, &jpgHeight, bytes.get(), static_cast<uint32_t>(received)) != JDR_OK ||
      jpgWidth != JPEG_WIDTH || jpgHeight != JPEG_HEIGHT) {
    Serial.printf("Unexpected JPEG geometry: %ux%u (expected %ux%u)\n",
                  jpgWidth, jpgHeight, JPEG_WIDTH, JPEG_HEIGHT);
    showMessage("Niewlasciwy rozmiar JPEG", TFT_RED);
    http.end();
    return;
  }
  jpegGeometryError = false;
  jpegPixelsWritten = 0;
  // Clear stale fragments before decoding; pushImage handles its own SPI
  // transactions, so do not nest manual tft.startWrite()/endWrite() calls.
  tft.fillScreen(TFT_BLACK);
  const JRESULT result = TJpgDec.drawJpg(0, 0, bytes.get(), static_cast<uint32_t>(received));
  const bool fullFrame = (jpegPixelsWritten == static_cast<uint32_t>(JPEG_WIDTH) * JPEG_HEIGHT);
  if (result == JDR_OK && !jpegGeometryError && fullFrame) {
    lastEtag = etag;
    waitingForPtzImage=false;
    Serial.printf("New landscape JPEG: %u bytes; directly drawn at 320x240\n",
                  static_cast<unsigned>(received));
  } else {
    Serial.printf("JPEG error: %d (geometry %d, pixels %lu/%lu)\n",
                  static_cast<int>(result), static_cast<int>(jpegGeometryError),
                  static_cast<unsigned long>(jpegPixelsWritten),
                  static_cast<unsigned long>(JPEG_WIDTH) * JPEG_HEIGHT);
    // The HTTP ETag must NOT advance on an incomplete frame.
    tft.fillScreen(TFT_BLACK);
    writeScreenLine("JPEG niepelny", 8, TFT_RED);
    writeScreenLine("Sprobuj ponownie", 38, TFT_YELLOW);
  }
  http.end();
}

void ptzBanner(const String& message,uint16_t color){
  tft.fillRect(0,0,tft.width(),25,TFT_BLACK);
  tft.setTextColor(color,TFT_BLACK);
  tft.drawString(message,8,4,2);
}
bool sendPtz(const char* direction){
  if(WiFi.status()!=WL_CONNECTED||haHost.isEmpty()||snapshotToken.isEmpty())return false;
  WiFiClient client;
  HTTPClient http;
  if(!http.begin(client,"http://"+haHost+":8100/ptz"))return false;
  http.setReuse(false);http.setTimeout(4000);
  http.addHeader("X-UBox-Token",snapshotToken);
  http.addHeader("Content-Type","application/json");
  const String json=String("{\"direction\":\"")+direction+"\"}";
  const int response=http.POST(json);http.end();
  if(response!=202){
    Serial.printf("PTZ rejected HTTP %d\n",response);
    ptzBanner(response==409?"PTZ zajety":"Blad PTZ",TFT_YELLOW);
    return false;
  }
  ptzBanner("Ruch: "+String(direction)+"...",TFT_CYAN);
  waitingForPtzImage=true;
  ptzImageDeadline=millis()+PTZ_REFRESH_TIMEOUT_MS;
  lastPoll=0;
  return true;
}
void checkTouch(){
  if(!touchReady||!touchCalibrated)return;
  int16_t x=0,y=0;
  const bool pressed=readTouchXY(x,y);
  const unsigned long now=millis();
  if(pressed){
    if(!touching){
      touching=true;dragStartX=x;dragStartY=y;
      dragCurrentX=x;dragCurrentY=y;dragStartMs=now;
    }else{dragCurrentX=x;dragCurrentY=y;}
  }else if(touching){
    touching=false;
    const int dx=dragCurrentX-dragStartX,dy=dragCurrentY-dragStartY;
    const unsigned long duration=now-dragStartMs;
    if(duration<90||duration>2100||now<gestureNextAllowed||waitingForPtzImage)return;
    const int ax=abs(dx),ay=abs(dy);
    if(ax<38&&ay<38)return;
    const char* direction=nullptr;
    if(ax>ay*1.25f)direction=dx>0?"right":"left";
    else if(ay>ax*1.25f)direction=dy>0?"down":"up";
    if(direction){gestureNextAllowed=now+6500UL;sendPtz(direction);}
  }
}

bool brightnessAnchorsValid() {
  return lightNight.raw>=0&&lightNight.raw<=4095&&
      lightDay.raw>=0&&lightDay.raw<=4095&&
      abs(lightDay.raw-lightNight.raw)>=25 &&
      lightNight.percent>=5&&lightNight.percent<=100&&
      lightDay.percent>=5&&lightDay.percent<=100;
}
void loadBrightnessNVS(){
  Preferences prefs;
  if(!prefs.begin("ubox-cyd",true))return;
  if(prefs.getBool("br_ok",false)){
    lightNight.raw=prefs.getInt("br_nraw",-1);
    lightNight.percent=prefs.getInt("br_npct",100);
    lightDay.raw=prefs.getInt("br_draw",-1);
    lightDay.percent=prefs.getInt("br_dpct",100);
  }
  prefs.end();
  brightnessCalibrated=brightnessAnchorsValid();
}
void saveBrightnessNVS(){
  Preferences prefs;
  if(!prefs.begin("ubox-cyd",false))return;
  prefs.putBool("br_ok",brightnessCalibrated);
  if(brightnessCalibrated){
    prefs.putInt("br_nraw",lightNight.raw);
    prefs.putInt("br_npct",lightNight.percent);
    prefs.putInt("br_draw",lightDay.raw);
    prefs.putInt("br_dpct",lightDay.percent);
  }
  prefs.end();
}
float brightnessTarget(){
  if(previewPercent>=5&&static_cast<int32_t>(previewUntil-millis())>0)
    return float(previewPercent);
  previewPercent=-1;
  if(!brightnessConfigSeen||!brightnessCalibrated||!ldrValid)return 100.0f;
  const float ratio=constrain((filteredLdr-lightNight.raw)/
      float(lightDay.raw-lightNight.raw),0.0f,1.0f);
  return constrain(lightNight.percent+ratio*(lightDay.percent-lightNight.percent),
                   5.0f,100.0f);
}
void updateBrightness(){
  const unsigned long now=millis();
  if(!ldrValid||now-lastLightSample>=LDR_SAMPLE_MS){
    lastLightSample=now;
    uint32_t sum=0;
    for(int i=0;i<8;++i)sum+=analogRead(LDR_ADC_PIN);
    float avg=sum/8.0f;
    if(!ldrValid){filteredLdr=avg;ldrValid=true;}
    else filteredLdr=filteredLdr*0.72f+avg*0.28f;
  }
  const float desired=brightnessTarget();
  const float delta=constrain(desired-currentBrightness,-0.6f,0.6f);
  currentBrightness=constrain(currentBrightness+delta,5.0f,100.0f);
  const int duty=constrain(int(roundf(currentBrightness*255.0f/100.0f)),13,255);
  if(backlightPwmReady)ledcWrite(TFT_BACKLIGHT_PIN,duty);
  else digitalWrite(TFT_BACKLIGHT_PIN,HIGH); // PWM failure must never blank the panel.
}
void getBrightnessConfig(){
  if(WiFi.status()!=WL_CONNECTED||haHost.isEmpty()||snapshotToken.isEmpty())return;
  WiFiClient client;
  HTTPClient http;
  if(!http.begin(client,"http://"+haHost+":8100/brightness-config.json"))return;
  http.setReuse(false);http.setTimeout(2200);
  http.addHeader("X-UBox-Token",snapshotToken);
  int code=http.GET();
  if(code==HTTP_CODE_OK){
    StaticJsonDocument<384> doc;
    if(!deserializeJson(doc,http.getStream())){
      brightnessConfigSeen=true; // Allow calibration only after first valid HA response.
      auto night=doc["night"];
      auto day=doc["day"];
      const bool valid=night.is<JsonObject>()&&day.is<JsonObject>()&&
         night["raw"].is<int>()&&night["percent"].is<int>()&&
         day["raw"].is<int>()&&day["percent"].is<int>();
      const int nRaw=valid?night["raw"].as<int>():-1;
      const int dRaw=valid?day["raw"].as<int>():-1;
      const int nPercent=valid?night["percent"].as<int>():100;
      const int dPercent=valid?day["percent"].as<int>():100;
      const bool newValid=valid&&nRaw>=0&&nRaw<=4095&&dRaw>=0&&dRaw<=4095&&
          abs(nRaw-dRaw)>=25&&nPercent>=5&&nPercent<=100&&
          dPercent>=5&&dPercent<=100;
      if(newValid){
        if(!brightnessCalibrated||lightNight.raw!=nRaw||lightDay.raw!=dRaw||
           lightNight.percent!=nPercent||lightDay.percent!=dPercent){
          lightNight.raw=nRaw;lightDay.raw=dRaw;
          lightNight.percent=nPercent;lightDay.percent=dPercent;
          brightnessCalibrated=true;
          saveBrightnessNVS();
        }
      }else if(brightnessCalibrated){
        brightnessCalibrated=false;
        saveBrightnessNVS();
      }
      const int preview=doc["preview_percent"]|0;
      const int ms=doc["preview_ms"]|0;
      if(preview>=5&&preview<=100&&ms>0&&ms<=30000){
        previewPercent=preview;
        previewUntil=millis()+unsigned(ms);
      }else{
        previewPercent=-1;
      }
    }
  }
  http.end();
}
void postBrightnessTelemetry(){
  if(!ldrValid||WiFi.status()!=WL_CONNECTED||haHost.isEmpty()||snapshotToken.isEmpty())return;
  WiFiClient client;
  HTTPClient http;
  if(!http.begin(client,"http://"+haHost+":8100/brightness-telemetry"))return;
  http.setReuse(false);http.setTimeout(2200);
  http.addHeader("X-UBox-Token",snapshotToken);
  http.addHeader("Content-Type","application/json");
  const int raw=constrain(int(roundf(filteredLdr)),0,4095);
  const int percent=constrain(int(roundf(currentBrightness)),5,100);
  String data=String("{\"raw\":")+raw+",\"percent\":"+percent+"}";
  const int code=http.POST(data);
  if(code!=HTTP_CODE_OK)Serial.printf("Brightness telemetry: HTTP %d\n",code);
  http.end();
}

void setup() {
  Serial.begin(115200);
  pinMode(BOOT_BUTTON_PIN, INPUT_PULLUP);
  // Full brightness before the TFT, Wi-Fi portal, HA or NVS can intervene.
  pinMode(TFT_BACKLIGHT_PIN,OUTPUT);
  digitalWrite(TFT_BACKLIGHT_PIN,HIGH);
  pinMode(LDR_ADC_PIN,INPUT);
  analogReadResolution(12);
  analogSetPinAttenuation(LDR_ADC_PIN,ADC_11db);
  loadBrightnessNVS();
  // Load the saved orientation BEFORE drawing anything so the setup
  // menu, Wi-Fi progress and camera image are ALWAYS in one orientation.
  loadSettings();
  tft.init();
  tft.setRotation(screenRotation); // 320x240, default USB at right-lower corner
  // TFT_eSPI can configure the backlight GPIO during init: attach PWM afterwards.
  digitalWrite(TFT_BACKLIGHT_PIN,HIGH);
  backlightPwmReady=ledcAttach(TFT_BACKLIGHT_PIN,5000,8); // Arduino-ESP32 3.x
  if(backlightPwmReady)ledcWrite(TFT_BACKLIGHT_PIN,255);
  else {pinMode(TFT_BACKLIGHT_PIN,OUTPUT);digitalWrite(TFT_BACKLIGHT_PIN,HIGH);}
#if defined(ST7789_DRIVER)
  Serial.printf("CYD LCD ST7789, BL GPIO%d, PWM=%s\n",TFT_BACKLIGHT_PIN,
                backlightPwmReady?"ok":"fallback high");
#else
  Serial.printf("CYD LCD ILI9341, BL GPIO%d, PWM=%s\n",TFT_BACKLIGHT_PIN,
                backlightPwmReady?"ok":"fallback high");
#endif
  displaySelfTest();
  touchSPI.begin(25,39,32,33);
  touchReady=touch.begin(touchSPI);
  touch.setRotation(0);
  loadTouchCalibration();
  if(touchReady&&!touchCalibrated)calibrateTouch();
  TJpgDec.setJpgScale(1);
  TJpgDec.setSwapBytes(true);
  TJpgDec.setCallback(tftBlock);
  writeScreenLine("UBox CYD - start...", 8);
  configureNetworking(false);
}

void loop() {
  // Hold BOOT for 5s AFTER booting (not during reset) to reconfigure.
  // Pressing BOOT during reset instead enters ESP32 flashing mode.
  // Brief BOOT press: toggle between the two landscape directions (1/3).
  // Hold for 5 s while running: reset Wi-Fi/HA provisioning.
  if (digitalRead(BOOT_BUTTON_PIN) == LOW) {
    if (!bootHeldFrom) bootHeldFrom = millis();
    if (!buttonResetTriggered && millis() - bootHeldFrom >= 5000) {
      buttonResetTriggered = true;
      resetProvisioning();
    }
  } else if (bootHeldFrom) {
    const unsigned long held = millis() - bootHeldFrom;
    bootHeldFrom = 0;
    if(!buttonResetTriggered&&held>=2100&&held<4900){
      calibrateTouch();lastEtag="";lastPoll=0;
    }else if (!buttonResetTriggered && held >= 70 && held < 1800) {
      screenRotation = (screenRotation == 3) ? 1 : 3;
      saveRotation(screenRotation);
      tft.setRotation(screenRotation);
      tft.fillScreen(TFT_BLACK);
      writeScreenLine("Obrot: " + String(screenRotation), 8, TFT_CYAN);
      lastEtag = ""; // force image redraw at the new hardware orientation
      lastPoll = 0;
      Serial.printf("Display orientation: %u\n", (unsigned)screenRotation);
    }
  }
  if (WiFi.status() != WL_CONNECTED) {
    if (millis() - lastReconnect > 10000) {
      lastReconnect = millis();
      WiFi.reconnect();
    }
  }
  checkTouch();
  updateBrightness();
  if(WiFi.status()==WL_CONNECTED && !haHost.isEmpty() && !snapshotToken.isEmpty()){
    const unsigned long now=millis();
    if(lastBrightnessSync==0||now-lastBrightnessSync>=BRIGHTNESS_SYNC_MS){
      lastBrightnessSync=now;
      getBrightnessConfig();
    }
    if(lastBrightnessTelemetry==0||now-lastBrightnessTelemetry>=BRIGHTNESS_SYNC_MS){
      lastBrightnessTelemetry=now;
      postBrightnessTelemetry();
    }
  }
  if(waitingForPtzImage&&static_cast<int32_t>(millis()-ptzImageDeadline)>=0){
    waitingForPtzImage=false;
    ptzBanner("PTZ: brak nowego zdjecia",TFT_YELLOW);
  }
  const unsigned long interval=waitingForPtzImage?PTZ_POLL_MS:REFRESH_MS;
  if (lastPoll == 0 || millis() - lastPoll >= interval) {
    lastPoll = millis();
    pollImage();
  }
  delay(45);
}
