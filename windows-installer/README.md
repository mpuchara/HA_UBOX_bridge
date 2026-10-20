# Windows — instalator CYD 0.2.7 (portable)

Bez Pythona, PlatformIO ani praw administratora. Wymaga Chrome/Edge, Web Serial, kabla USB do danych i połączenia przeglądarki z internetem (skrypt ESP Web Tools z CDN).

[← README](../README.md) · [Pełna instrukcja CYD](../docs/CYD_WEB_INSTALL.md)

## Instalacja

1. Pobierz [UBox CYD 0.2.6 — Release](https://github.com/mpuchara/HA_UBOX_bridge/releases/tag/cyd-v0.2.6-fe27042c), plik `UBox-CYD-Windows-Browser-Installer.zip`.
2. **Wypakuj wszystko** do folderu (nie uruchamiaj z podglądu ZIP).
3. Podłącz CYD przez USB do Windows.
4. Uruchom `Start-Installer.cmd`. Skrypt `Install-CYD.ps1` uruchamia stronę lokalną pod `http://127.0.0.1:8765` (lub 8766–8770, jeśli port jest zajęty) i otwiera Edge.
5. Wybierz **ST7789** (sprawdzony na dwuportowej odmianie) albo **ILI9341**. Wybierz faktyczny port płytki; **COM4 to tylko przykład**.
6. Nie zamykaj okna konsoli do ukończenia wgrywania. Flashowanie może usunąć poprzednią konfigurację ESP32.
7. Po restarcie sprawdź test kolorów i połącz się z siecią **CYD / 12345678**. Portal Wi-Fi: **http://192.168.4.1**.

Wpisz domowe Wi-Fi **2,4 GHz**, adres IP hosta Home Assistant (bez `http://` i `:8123`) oraz **sam token** z panelu UBox Bridge. Firmware 0.2.6 wymaga Bridge **0.5.10+** dla PTZ (zalecany **0.5.12**).

## Po instalacji

CYD pobiera zdjęcia 320×240 z cache HA bez budzenia LTE. Przy pierwszym starcie skalibruj 3 punkty dotyku. Gesty na zdjęciu sterują PTZ. BOOT 2–4 s uruchamia ponowną kalibrację, ≥5 s resetuje Wi-Fi/HA. Opis: [CYD_WEB_INSTALL.md](../docs/CYD_WEB_INSTALL.md).

## Bezpieczeństwo

Lokalny serwer HTTP działa **tylko na 127.0.0.1** i akceptuje tylko GET do dozwolonych plików instalacyjnych. Nie przechwytuje haseł ani tokenów; użytkownik wpisuje je dopiero w konfiguratorze CYD. Wi-Fi `CYD / 12345678` ma słabe hasło — konfiguruj wyłącznie w zaufanym miejscu.

Jeśli przeglądarka nie widzi portu: sprawdź przewód USB z transmisją danych, sterownik USB-serial, uprawnienia Chrome/Edge i zamknij inne aplikacje używające COM.
