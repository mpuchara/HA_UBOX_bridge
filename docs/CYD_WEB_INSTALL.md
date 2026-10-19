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

## Firmware 0.2.3 — nowy sposób renderowania

Zaktualizuj UBox Bridge do 0.5.3, zrób nowe zdjęcie. Wgraj CYD 0.2.3.
Wyszukaj sieć Wi-Fi **CYD** i wpisz ośmioznakowe losowe hasło z LCD.
Panel konfiguracji: `http://192.168.4.1`. Dane sieci domowej i token HA
zapisują się w NVS, o ile przy flashowaniu nie wybrano kasowania pamięci.

## v0.2.4 — ułożenie montażowe CYD

**Najpierw UBox Bridge 0.5.5 i nowe zdjęcie.** Wgraj firmware 0.2.4.
Ułóż CYD poziomo z USB przy prawym dolnym rogu. Domyślny obrót LCD: 3;
krótkie naciśnięcie BOOT przełącza 1 ↔ 3, gdyby montaż odwrócił tekst.
Dłuższe BOOT (5 s) resetuje konfigurację Wi-Fi i HA.
AP `CYD`, hasło `12345678` (łatwe do odgadnięcia, tylko na czas konfiguracji).
W chwili uruchamiania sprawdź pola testowe LCD, niezależne od obrazu kamery.

## Wybór sterownika CYD v0.2.5 — dwa gniazda USB

Płytka ESP32-2432S028 z dwoma portami USB może mieć sterownik ST7789 zamiast
ILI9341. W instalatorze jest **ST7789 (zalecany pierwszy test)** i
**ILI9341 (alternatywa)**. Sprawdź po uruchomieniu cztery kolorowe pola
z oznaczeniem sterownika. Jeśli widzisz poprzednie piksele/pasy, spróbuj
drugiego sterownika. Nie trzeba wymieniać płytki.

Zaktualizuj najpierw UBox Bridge do 0.5.6, wykonaj nowe zdjęcie.
Od tej wersji obrót o 90° w lewo dotyczy także właściwego zdjęcia,
nie tylko menu LCD. W konfiguracji dodatku jest `camera_rotation: 90`.
Sieć AP: `CYD`, hasło `12345678` (słabe; uruchamiaj tylko na czas konfiguracji).

## Sterowanie PTZ gestami (CYD 0.2.6 / Bridge 0.5.10)

Zaktualizuj najpierw **UBox Bridge 0.5.10**. Wgraj CYD 0.2.6
(ST7789 albo ILI9341 — wybierz dotychczas działający kontroler).
Podczas pierwszego uruchomienia dotknij 3 krzyżyków na wyświetlaczu,
aby zapisać kalibrację XPT2046. Później przesunięcie palcem po obrazie
(>38 px) oznacza jeden krótki ruch kamery + STOP i nowy obraz.
BOOT 2–4 sekundy — ponowna kalibracja dotyku. Krótko — obrót LCD,
5 sekund — reset konfiguracji. Port 8100 pozostaje tylko w sieci LAN.
