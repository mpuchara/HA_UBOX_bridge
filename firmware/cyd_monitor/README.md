# UBox CYD Monitor v0.2.6 — dotykowe sterowanie PTZ

**Wymaga UBox Bridge 0.5.10+** (wersja 0.5.8 i starsze nie obsługują POST /ptz).
Wgraj aktualny firmware poprzez instalator w przeglądarce lub Windows ZIP.

- Przy pierwszym uruchomieniu pojawią się 3 krzyżyki. Dotknij każdego,
  by skalibrować oporowy panel XPT2046. Kalibracja zostaje zapisana
  w NVS. Jeśli nikogo nie ma przy kamerze, kalibracja wygaśnie po czasie
  i przeglądanie zdjęć nadal będzie działało.
- W widoku zdjęcia przesuń palec w dowolną stronę na co najmniej ~38 px.
  Jedno przeciągnięcie = krótki ruch (~420 ms) + STOP kamery, a następnie
  pobranie nowej klatki do HA. CYD sprawdza ją co 2.5 sekundy do 110 s.
  Jeżeli aparat nie obsługuje komendy, podgląd pozostaje z ostatnim zdjęciem.
- Przytrzymaj **BOOT przez 2–4 s**, aby ponownie skalibrować dotyk.
  Krótkie naciśnięcie BOOT obraca cały ekran o 180°, długie (5 s)
  resetuje ustawienia Wi-Fi.
- Nazwa AP **CYD**, hasło **12345678** (słabe; uruchamiaj AP wyłącznie
  podczas konfiguracji w zaufanym otoczeniu).

Piny XPT2046: SCLK 25, MISO 39, MOSI 32, CS 33, IRQ 36.
Touch komunikuje się osobną magistralą SPI niż LCD, więc nie koliduje
z odświeżaniem JPEG. Dostępne dwa warianty firmware ST7789 i ILI9341;
zachowaj wariant, na którym wyświetlacz już działał poprawnie.

Uwaga: wsparcie PTZ przez P4P jest eksperymentalne. Samo przyjęcie żądania
nie potwierdza jeszcze fizycznego ruchu XEGA XG-01-EU4G. Mostek nigdy
nie udostępnia komend surowych ani oświetlenia w tej wersji.
