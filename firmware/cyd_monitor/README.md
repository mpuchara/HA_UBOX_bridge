# CYD Monitor — firmware 0.2.8

**Obsługiwany sprzęt:** ESP32-2432S028 (2,8″, 240×320) z dotykiem XPT2046. **Zalecany dodatek Home Assistant: UBox Bridge 0.5.13**; dla gestów PTZ minimum 0.5.10.

[← README](../../README.md) · [Instalacja krok po kroku](../../docs/CYD_WEB_INSTALL.md) · [Diagnostyka](../../docs/TROUBLESHOOTING.md)

## Funkcje

- Wyświetla JPEG 320×240 w poziomie, pobierany z `http://IP_HA:8100/snapshot-cyd-wide.jpg`. Złącza USB po prawej, bliżej dołu (krótkim BOOT można obrócić cały LCD o 180°).
- Odpytuje bufor HA co 30 s z `If-None-Match` / ETag; sprawdzenie nie budzi kamery LTE.
- Rozpoznaje gesty lewo/prawo/góra/dół na XPT2046 i wywołuje w HA krótki ruch PTZ + STOP + odświeżenie klatki. Po ruchu sprawdza zdjęcie co 2,5 s do 110 s.
- Zachowuje kalibrację dotyku i konfigurację Wi-Fi w pamięci NVS.
- Ma trzy profile: **ST7789/GPIO27**, **ST7789/GPIO21** oraz **ILI9341/GPIO21**. Rewizje z dwoma gniazdami USB różnią się pinem podświetlenia.

## Instalacja z przeglądarki / Windows ZIP

Otwórz **https://mpuchara.github.io/HA_UBOX_bridge/** w Chrome/Edge na komputerze z podłączonym ESP32. Wybierz ST7789 albo ILI9341 i poprawny port COM.

Jeśli strona jest niedostępna lub potrzebujesz instalatora lokalnego, pobierz [CYD 0.2.8 — Windows ZIP](https://github.com/mpuchara/HA_UBOX_bridge/releases), wypakuj i uruchom `Start-Installer.cmd`. Instrukcja: [CYD_WEB_INSTALL.md](../../docs/CYD_WEB_INSTALL.md).

Po pierwszym uruchomieniu sprawdź **cztery pola kolorów**. W białym polu wyświetla się używany pin podświetlenia. Ekran jest włączony na 100% jeszcze bez sieci HA. Jeśli mimo tego jest czarny, ale widzisz Wi-Fi `CYD`, przetestuj drugi profil GPIO. Jeżeli obraz jest wadliwy, zmień wariant sterownika, zanim zaczniesz diagnozować kamerkę.

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

## Podświetlenie LCD / czujnik LDR

Od firmware 0.2.8 GPIO21 steruje podświetleniem przez PWM, a GPIO34 (ADC1) mierzy fotorezystor. Po założeniu obudowy w panelu UBox Bridge wybierz dwa punkty **Noc** i **Dzień**, zapisując faktyczny odczyt i wybrany procent jasności. ESP32 interpoluje pomiędzy nimi, wygładza pomiar i zapisuje punkty w NVS. [Kalibracja krok po kroku](../../docs/BRIGHTNESS_CALIBRATION.md).

## Kompilacja ze źródeł

Projekt PlatformIO: [platformio.ini](platformio.ini). W katalogu głównym repo:

~~~sh
pio run -d firmware/cyd_monitor
~~~

Środowiska: `esp32-2432s028` (**ST7789/GPIO27**), `esp32-2432s028-st7789-gpio21` (**ST7789/GPIO21**), `esp32-2432s028-ili9341` (**ILI9341/GPIO21**).

| Podzespół | GPIO |
| --- | --- |
| TFT: MOSI/MISO/CLK/CS/DC/BL | 13/12/14/15/2/27 lub 21 (według profilu) |
| Touch: CLK/MISO/MOSI/CS/IRQ | 25/39/32/33/36 |
| BOOT | 0 |

Dotyk korzysta z osobnej magistrali SPI. Poświadczenia Wi-Fi i token nie są zapisane w kodzie ani udostępniane na GitHubie. **Nie otwieraj portu HA 8100 do internetu.**
