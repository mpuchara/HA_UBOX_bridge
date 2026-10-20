# CYD Monitor — firmware 0.2.6

**Obsługiwany sprzęt:** ESP32-2432S028 (2,8″, 240×320) z dotykiem XPT2046. **Zalecany dodatek Home Assistant: UBox Bridge 0.5.12**; dla gestów PTZ minimum 0.5.10.

[← README](../../README.md) · [Instalacja krok po kroku](../../docs/CYD_WEB_INSTALL.md) · [Diagnostyka](../../docs/TROUBLESHOOTING.md)

## Funkcje

- Wyświetla JPEG 320×240 w poziomie, pobierany z `http://IP_HA:8100/snapshot-cyd-wide.jpg`. Złącza USB po prawej, bliżej dołu (krótkim BOOT można obrócić cały LCD o 180°).
- Odpytuje bufor HA co 30 s z `If-None-Match` / ETag; sprawdzenie nie budzi kamery LTE.
- Rozpoznaje gesty lewo/prawo/góra/dół na XPT2046 i wywołuje w HA krótki ruch PTZ + STOP + odświeżenie klatki. Po ruchu sprawdza zdjęcie co 2,5 s do 110 s.
- Zachowuje kalibrację dotyku i konfigurację Wi-Fi w pamięci NVS.
- Ma dwie wersje sterownika: **ST7789** (pierwszy test na dwuportowej płytce) oraz **ILI9341** (alternatywa).

## Instalacja z przeglądarki / Windows ZIP

Otwórz **https://mpuchara.github.io/HA_UBOX_bridge/** w Chrome/Edge na komputerze z podłączonym ESP32. Wybierz ST7789 albo ILI9341 i poprawny port COM.

Jeśli strona jest niedostępna lub potrzebujesz instalatora lokalnego, pobierz [CYD 0.2.6 — Windows ZIP](https://github.com/mpuchara/HA_UBOX_bridge/releases/tag/cyd-v0.2.6-fe27042c), wypakuj i uruchom `Start-Installer.cmd`. Instrukcja: [CYD_WEB_INSTALL.md](../../docs/CYD_WEB_INSTALL.md).

Po pierwszym uruchomieniu sprawdź **cztery pola kolorów**. Jeżeli obraz jest wadliwy, zmień wariant sterownika, zanim zaczniesz diagnozować kamerkę.

## Konfiguracja Wi-Fi

AP konfiguratora: **CYD** / **12345678** (słabe hasło; używaj krótko, w zaufanej sieci). Portal: **http://192.168.4.1**.

Ustaw Wi-Fi 2,4 GHz, lokalny IP Raspberry Pi **bez portu i protokołu**, oraz **sam token** z UBox Bridge → Zaawansowane. Nie wklejaj całego URL zdjęcia.

## Kalibracja, gesty i przycisk BOOT

Przy pierwszym uruchomieniu dotknij **3 żółtych krzyżyków**. Bez kalibracji obraz działa, ale gesty PTZ nie muszą działać.

| Naciśnięcie BOOT podczas normalnej pracy | Funkcja |
| --- | --- |
| Krótkie: około 0,07–1,8 s | Obrót LCD 180° (zapamiętany) |
| 2,1–4,9 s | Ponowna kalibracja XPT2046 |
| ≥5 s | Reset Wi-Fi/IP/tokenu, otwarcie konfiguratora |

Nie wciskaj BOOT podczas włączania/resetu (ESP32 może wejść w tryb bootloadera).

Gest po zdjęciu >~38 px w jednym kierunku = **jeden ruch** (nie ciągły joystick). Czas ruchu ustawia dodatek HA: domyślnie `ptz_pulse_ms: 100` i `ptz_speed: 1`. Ruchy i STOP są eksperymentalne dla różnych firmware kamer UBox.

## Kompilacja ze źródeł

Projekt PlatformIO: [platformio.ini](platformio.ini). W katalogu głównym repo:

~~~sh
pio run -d firmware/cyd_monitor
~~~

Środowiska: `esp32-2432s028` (**ST7789**), `esp32-2432s028-ili9341` (**ILI9341**).

| Podzespół | GPIO |
| --- | --- |
| TFT: MOSI/MISO/CLK/CS/DC/BL | 13/12/14/15/2/21 |
| Touch: CLK/MISO/MOSI/CS/IRQ | 25/39/32/33/36 |
| BOOT | 0 |

Dotyk korzysta z osobnej magistrali SPI. Poświadczenia Wi-Fi i token nie są zapisane w kodzie ani udostępniane na GitHubie. **Nie otwieraj portu HA 8100 do internetu.**
