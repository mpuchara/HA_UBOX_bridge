# Bezpieczeństwo, prywatność i oszczędzanie baterii

[← README](../README.md) · [Instalacja](INSTALL_HA.md) · [Android](ANDROID_WIDGET.md)

UBox Bridge to **eksperymentalny mostek P4P**, nie oficjalna integracja UBox. Przetwarza poświadczenia pozwalające uzyskać obraz i sterować **fizycznym ruchem kamery**. Używaj tylko do własnych urządzeń i w zaufanej sieci.

## Gdzie są dane?

- **Login UBox / hasło konta / hasło urządzenia:** zapisane w konfiguracji dodatku Home Assistant OS. Nie wrzucaj ich do Git, publicznych logów ani zgłoszeń.
- **Token UBox Bridge:** tworzony na hoście HA w `/data/snapshot_token`, dostępny w panelu Ingress. Uwierzytelnia **odczyt obrazu oraz ruch PTZ** przez port 8100.
- **CYD:** przechowuje Wi-Fi, IP hosta i token w pamięci NVS ESP32. Flashowanie z kasowaniem pamięci może wymagać ponownego wpisania danych.
- **Generic Camera:** jeśli korzysta z URL `?token=…`, token jest przechowywany w konfiguracji HA. Traktuj pełny URL jako sekret.
- **Panel Ingress:** dostępny przez uwierzytelnioną sesję Home Assistant, zamiast niezabezpieczonego interfejsu na porcie 8100.

## Konieczne zabezpieczenia

1. **Nie przekierowuj TCP 8100** na routerze i nie publikuj go przez publiczny reverse proxy.
2. Zapewnij dostęp do portu 8100 wyłącznie z potrzebnych urządzeń w zaufanej sieci lokalnej.
3. Nie umieszczaj tokenów/poświadczeń w publicznych zrzutach, README, issue i automatyzacjach publikowanych w sieci.
4. Po wycieku tokenu wybierz w panelu **Zaawansowane → Wygeneruj nowy token**; następnie popraw konfigurację CYD, Generic Camera i `secrets.yaml` akcji PTZ.
5. Punkt dostępowy CYD ma **SSID `CYD` / hasło `12345678`**. To ustawienie na życzenie użytkownika, ale jest **łatwe do odgadnięcia**. Uruchamiaj AP tylko na czas konfiguracji, w zaufanym otoczeniu; nie konfiguruj urządzenia w miejscu publicznym.
6. Dla dostępu do zdjęć z Androida poza domem skorzystaj z **HA Cloud lub VPN**. Zewnętrzny dostęp do samego HA nie wymaga wystawiania portu 8100.

## Ochrona kamery solarnej i danych LTE

- Sprawdzanie istniejącego JPEG przez CYD lub Generic Camera **nie** budzi kamery.
- **Każde Nowe zdjęcie**, harmonogram lub **PTZ z odświeżeniem** otwiera sesję P4P i może zużyć energię i transfer LTE.
- `interval_minutes: 15` = maksymalnie około **96 prób pobierania na dobę**, jeżeli dodatek pracuje stale; dla kamery solarnej rozpocznij od **30–60 min** i obserwuj baterię.
- Ruchy PTZ są krótkie, mają STOP i blokadę nakładania, ale kamera może zareagować z opóźnieniem lub inaczej, niż oczekiwano.
- Nie uruchamiaj „stress testów” ciągłego PTZ ani przechwytywania co kilka sekund na baterii solarnej.

## Token i API

**Odczyt JPEG:** `GET http://IP_HA:8100/snapshot-cyd-wide.jpg` z nagłówkiem `X-UBox-Token: TOKEN`; Generic Camera obsługuje również parametr `?token=TOKEN`.

**Sterowanie ruchem:** `POST http://IP_HA:8100/ptz` z nagłówkiem `X-UBox-Token: TOKEN` i ograniczonym JSON, np. `{"direction":"left"}`. Token w URL **nie** autoryzuje zapisu PTZ. Nie ma publicznego API do swobodnych komend IOCTRL.

**Dopasowanie kadru:** `POST /framing` działa **wyłącznie w HA Ingress** (przez zalogowanego użytkownika). Nie jest wystawione do sieci LAN.

## Uwaga na upstream

Kod komunikacji P4P opiera się na przypiętym commicie [asyrk/ubox-web](https://github.com/asyrk/ubox-web), a część komend PTZ na reverse engineeringu. Kompatybilność i bezpieczeństwo takiego protokołu nie są gwarantowane. Aktualizuj dodatki, pilnuj uprawnień HA i ogranicz dostęp do sieci.
