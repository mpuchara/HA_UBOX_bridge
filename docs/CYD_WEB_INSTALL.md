# CYD — instalacja z przeglądarki (Web Serial)

Instalator: https://mpuchara.github.io/HA_UBOX_bridge/

Pliki źródłowe strony i manifestu: `web-installer/`.
Strona jest publikowana automatycznie przez GitHub Actions
(`.github/workflows/cyd-web-installer.yml`) wraz z kompilowanym
`firmware/ubox-cyd-esp32.bin`.

**Jeżeli GitHub Pages nie jest jeszcze aktywne**, w ustawieniach repozytorium
wejdź w *Settings → Pages → Build and deployment → Source: GitHub Actions*.
Następnie uruchom ponownie workflow *Build and publish CYD browser installer*
(Actions → wybierz workflow → Run workflow).

1. Podłącz klasyczny CYD ESP32-2432S028 przez USB. Na Windows wybierz
   port COM4 (albo port wyświetlany w menedżerze urządzeń).
2. Otwórz URL na desktopowym Chrome/Edge (Web Serial wymaga HTTPS).
3. Kliknij przycisk instalacji i wskaż właściwy port. Uważaj, bo
   flashowanie może skasować dotychczasową zawartość ESP32.
4. Po restarcie zobaczysz na wyświetlaczu SSID `UBox-CYD-...` i losowe
   hasło sieci konfiguracyjnej.
5. Połącz telefon lub komputer z tą siecią i otwórz
   `http://192.168.4.1`. Wybierz lokalne Wi-Fi 2.4 GHz i wpisz
   adres IP Raspberry Pi/HA (bez https i :8123) i token zdjęć.
6. Po połączeniu CYD pobiera zdjęcie z
   `http://IP_HA:8100/snapshot.jpg`, przesyłając token w nagłówku
   HTTP. Co 30 sekund wykonuje zapytanie warunkowe `If-None-Match`.
7. Podgląd jest lokalny. UBox Bridge HA sam aktualizuje JPEG w ustawionym
   interwale. Sam CYD nigdy nie budzi kamery LTE.

## Ponowna konfiguracja
Po normalnym uruchomieniu CYD przytrzymaj przycisk BOOT ok. 5 sekund.
Urządzenie czyści zapisane Wi-Fi i token, restartuje się i pokazuje
nowe SSID z hasłem. **Nie wciskaj BOOT podczas włączania/RESET**, bo
wtedy ESP32 może wejść w tryb programowania.

## Rozdzielenie bezpieczeństwa
Strona GitHub Pages nie zbiera danych Wi-Fi, HA ani tokenów UBox.
Konfiguracja odbywa się wyłącznie przez losowo zabezpieczony hotspot
urządzenia. Token i konfiguracja HA zapisują się w NVS ESP32; token
przekazywany jest do HA lokalnym HTTP. Port 8100 NIE powinien być
wystawiany do internetu.

## Uwaga na model płytki
Ta kompilacja jest dla klasycznego ESP32-2432S028 (2.8-calowy ILI9341).
Nie instaluj na innych wariantach CYD (ESP32-S3, ESP32-P4 itp.).
Firmware działa z GPIO panelu klasycznego CYD, ale nie był jeszcze
testowany na fizycznej płytce tego użytkownika.

## Orientacja i pasy obrazu

Od wersji CYD 0.2.1 obraz 320×240 z HA jest obracany w ESP32 o 90° w lewo i rysowany jako 240×320 na pionowo ustawionym panelu. Taktowanie SPI wyświetlacza obniżono do 27 MHz, a transfer JPEG jest wykonywany jako jedna transakcja. Jeżeli pasy widać także w przeglądarce w panelu dodatku HA, ich przyczyną jest źródłowy strumień UBox, a nie sterownik CYD.
