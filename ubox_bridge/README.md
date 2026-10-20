# UBox Bridge 0.5.12 — dodatek Home Assistant OS

**Eksperymentalny mostek UBox P4P / XEGA 4G** działający na HA OS (`aarch64` i `amd64`). Nie jest to oficjalne SDK UBox.

[← README projektu](../README.md) · [Instalacja HA](../docs/INSTALL_HA.md) · [Obsługa panelu](../docs/USER_GUIDE.md) · [Android](../docs/ANDROID_WIDGET.md) · [API/architektura](DOCS.md) · [Bezpieczeństwo](../docs/SECURITY.md)

## Skrót instalacji

Dodaj repozytorium `https://github.com/mpuchara/HA_UBOX_bridge` w sklepie dodatków/aplikacji HA OS. Zainstaluj UBox Bridge, podaj login konta UBox albo UID+hasło P2P, uruchom, otwórz Ingress i naciśnij **Nowe zdjęcie**.

Do fotointerwału służy `interval_minutes`. W nowej instalacji domyślnie 15; starszy zapis `0` wyłącza harmonogram aż do ręcznej zmiany. Uważaj na zużycie baterii i LTE (15 minut = około 96 pobrań/dzień).

## Najważniejsze opcje

| Opcja | Domyślna | Efekt |
| --- | --- | --- |
| `video_quality` | `hd` | Żąda streamIndex 1; `sd` żąda 0, `manual` używa `stream_index`. |
| `capture_on_start` | `false` | Nie wybudza kamery po restarcie. |
| `cyd_fit_mode` | `blur` | **Lista** Blur/Cover/Contain. |
| `cyd_focus_x` | `50` | Pozycja przycięcia dla Cover: 0–100. |
| `ptz_pulse_ms` | `100` | Czas impulsu PTZ 60–350 ms. |
| `ptz_speed` | `1` | Prędkość PTZ 1–8. |

Panel wyświetla **jedno zdjęcie 320×240 na górze**, pod nim strzałki PTZ, przycisk nowego zdjęcia i wybór kadrowania. Zmiana trybu kadrowania przelicza JPEG z cache HA bez połączenia LTE i zapisuje `/data/framing.json`. **Wybór panelu ma pierwszeństwo przed opcją z konfiguracji dodatku.**

## Pliki w pamięci dodatku

- `/data/last.jpg` — źródłowy JPEG w rozdzielczości rzeczywiście odebranej.
- `/data/last_cyd_wide.jpg` — 320×240 dla CYD/Generic Camera.
- `/data/last_cyd.jpg` — stary wariant pionowy, tylko dla zgodności.
- `/data/snapshot_token` — token dostępu do zdjęć **i** PTZ.
- `/data/framing.json` — kadrowanie z panelu Ingress.

## API

**8099** to wyłącznie Ingress HA; **8100** to LAN z tokenem, przeznaczony dla CYD/Generic Camera. Obrazy GET: `/snapshot.jpg` (rozdzielczość źródła) i `/snapshot-cyd-wide.jpg` (320×240), metadane `/snapshot-meta.json`. PTZ: `POST /ptz` z nagłówkiem `X-UBox-Token` i JSON `{"direction":"left"}` (lub right/up/down).

HTTP GET do cache **nie budzi kamery**. Przycisk Nowe zdjęcie, harmonogram i PTZ wywołują sesję P4P, a po ruchu następuje STOP i próba nowego zdjęcia. Nie jest to strumień RTSP.

**Nie przekierowuj TCP 8100 na routerze** i nie publikuj tokenu. Szczegóły techniczne: [DOCS.md](DOCS.md), historia: [CHANGELOG.md](CHANGELOG.md).
