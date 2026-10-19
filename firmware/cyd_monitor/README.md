# UBox CYD Monitor — instalator przez przeglądarkę

**Najłatwiej:** otwórz https://mpuchara.github.io/HA_UBOX_bridge/
w Chrome/Edge na komputerze z podłączonym CYD (np. COM4).

Nie trzeba tworzyć pliku `config.h`, korzystać z PlatformIO ani
umieszczać danych Wi-Fi w kodzie.

Po instalacji CYD wyświetli SSID hotspotu `UBox-CYD-...` i losowe
hasło. Połącz telefon z hotspotem, wejdź na `http://192.168.4.1`,
wybierz Wi-Fi 2.4 GHz oraz wpisz IP Raspberry Pi z HA (bez portu)
i token UBox Bridge. Ustawienia zapiszą się w NVS ESP32.

Obraz z HA 320×240 jest obracany o 90° w lewo i wyświetlany na całym ekranie CYD 240×320. SPI wyświetlacza działa z 27 MHz, aby ograniczyć artefakty transmisji.\n\nCYD odpyta HA co 30 sekund. Gdy JPEG się nie zmienił, HA odpowie HTTP
304; sam odczyt zdjęcia nie uruchamia transmisji LTE.
Pobieranie świeżej klatki ustaw w dodatku HA `interval_minutes`.

Aby wyczyścić konfigurację, gdy CYD normalnie działa, przytrzymaj
przycisk BOOT około 5 sekund. Nie wciskaj BOOT podczas resetu, bo
możesz przejść w tryb flash.

Dla programistów: można nadal zbudować firmware bezpośrednio:
```sh
pio run -d firmware/cyd_monitor
pio run -d firmware/cyd_monitor -t upload --upload-port COM4
```

Ten firmware obsługuje klasyczny CYD ESP32-2432S028 z ILI9341.
Warianty o innych pinach mogą wymagać zmian `platformio.ini`.
Firmware przechowuje token w NVS i łączy się z HA przez lokalne HTTP,
dlatego nie wystawiaj portu HA 8100 na Internet.

Jeżeli poziome pasy pozostają, otwórz ostatni obraz w panelu UBox Bridge na telefonie. Jeżeli są widoczne także tam, pochodzą z niekompletnych klatek transmisji P4P i nie naprawi ich sterownik LCD.

Od firmware CYD v0.2.2 transmisja SPI do ILI9341 działa z prędkością 20 MHz
(zamiast 27 MHz). Obrót JPEG o 90° w lewo i pełne 240×320 zostały
wprowadzone w v0.2.1. Obraz w HA pozostaje w poziomie 320×240.

## Firmware 0.2.3 — pełny ekran

UBox Bridge v0.5.3+ obraca obraz 90° w lewo i udostępnia już gotowy JPEG
240×320 pod `/snapshot-cyd.jpg`. CYD rysuje go bez kolejnego obrotu.
Aby obraz zajął cały ekran, wejście jest centralnie przycinane do proporcji 4:3.
Nazwa hotspotu konfiguracyjnego: **CYD**. Hasło: **8 losowych czytelnych znaków**,
pokazane na ekranie (bez mylących liter I/O i cyfr 0/1). Hasło jest
jednorazowe dla sesji konfiguracyjnej i zabezpiecza hotspot WPA2.
Najpierw zaktualizuj dodatek do 0.5.3 i naciśnij 'Zrób nowe zdjęcie',
a dopiero później aktualizuj firmware CYD.
