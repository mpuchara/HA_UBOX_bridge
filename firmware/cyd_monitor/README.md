# UBox CYD Monitor v0.2.4 — poziomo, USB po prawej u dołu

[Instalator USB przez Chrome/Edge](https://mpuchara.github.io/HA_UBOX_bridge/) lub pakiet instalatora Windows z Releases.

**Wymaga dodatku UBox Bridge 0.5.5+**. Po aktualizacji dodatku wykonaj
przynajmniej jedno nowe zdjęcie z kamery, aby utworzyć `/snapshot-cyd-wide.jpg`.

CYD wyświetla w **320×240 poziomo**. Montuj go tak, aby przewód USB
wychodził w **prawej dolnej części**. Domyślnie sterownik LCD używa
`setRotation(3)`. Jeśli obraz wyjdzie do góry nogami, **naciśnij BOOT krótko**,
aby przełączyć na `setRotation(1)`. Wybrane ustawienie pozostaje zapisane
po restarcie. Przytrzymanie BOOT przez 5 sekund resetuje ustawienia połączenia.

Podczas włączania przez około 1,6 s widać cztery kolorowe pola testowe:
czerwone/zielone/niebieskie/białe. Jeżeli białe lub zaszumione pasy
pojawiają się już na polach testowych czy w komunikacie Wi-Fi, problem
nie pochodzi z obrazu UBox — sprawdź ekran, zasilanie i SPI.
Prędkość SPI zmniejszono do 10 MHz na potrzeby diagnostyki.

Sieć konfiguracyjna: `CYD`, hasło: `12345678`.
To celowo proste, **łatwe do odgadnięcia** hasło. Uruchamiaj tę sieć
tylko na czas konfiguracji, w zaufanym miejscu.
Otwórz `http://192.168.4.1` i podaj Wi-Fi 2.4 GHz, IP Raspberry Pi oraz token.
Po połączeniu z domową siecią AP przestaje działać.

CYD pobiera wyłącznie buforowany JPEG 320×240 z HA, nie łączy się
z LTE i nie budzi kamerki. Odpytuje co 30 s, używa ETag/304.
Token oraz konfiguracja Wi-Fi przechowywane są w NVS, nigdy w repozytorium.

## Historia i wcześniejsze warianty

# UBox CYD Monitor — instalator przez przeglądarkę

**Najłatwiej:** otwórz https://mpuchara.github.io/HA_UBOX_bridge/
w Chrome/Edge na komputerze z podłączonym CYD (np. COM4).

Nie trzeba tworzyć pliku `config.h`, korzystać z PlatformIO ani
umieszczać danych Wi-Fi w kodzie.

Po instalacji CYD wyświetli SSID hotspotu `UBox-CYD-...` i losowe
hasło. Połącz telefon z hotspotem, wejdź na `http://192.168.4.1`,
wybierz Wi-Fi 2.4 GHz oraz wpisz IP Raspberry Pi z HA (bez portu)
i token UBox Bridge. Ustawienia zapiszą się w NVS ESP32.

Obraz z HA 320×240 jest obracany o 90° w lewo i wyświetlany na całym ekranie CYD 240×320. CYD odpyta HA co 30 sekund. Gdy JPEG się nie zmienił, HA odpowie HTTP
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

Firmware CYD v0.2.3 nie wymaga aktualizacji po UBox Bridge v0.5.4.
Nowe zdjęcia są przygotowywane z rozdzielczości źródłowej przez HA,
nie z wcześniejszego JPEG 320×240.
