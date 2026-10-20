# UBox Bridge 0.5.13 — architektura i HTTP API

[← README](../README.md) · [Instrukcja obsługi](../docs/USER_GUIDE.md) · [Bezpieczeństwo](../docs/SECURITY.md)

## Komponenty

- `bridge.py` — stan, token, harmonogram, dwa serwery HTTP.
- `capture_live.js` — krótki odbiór P4P przez przypięty commit [asyrk/ubox-web](https://github.com/asyrk/ubox-web).
- `ptz_move.js` — impuls PTZ i STOP po P4P. Protokół nieoficjalny.
- `cloud_api.py` — wykrywanie kamery z konta UBox.
- `video_profiles.py` — `hd`→streamIndex 1; `sd`→0; `manual`→`stream_index`.
- `frame_quality.py` — wybór spośród zdekodowanych klatek.
- `image_filters.py` — skalowanie/kadrowanie do 320×240.
- FFmpeg/FFprobe — dekodowanie i weryfikacja rzeczywistej rozdzielczości.

```text
Zdarzenie: przycisk / harmonogram / po PTZ
  → P4P/HEVC/H264 → do 18 kandydatów do oceny jakości
  → ponowny dekod wybranej klatki w rozdzielczości źródła
  → /data/last.jpg (bez obrotu, natywna rozdzielczość)
  → /data/last_cyd_wide.jpg (320×240, blur/cover/contain)
  → HTTP: panel HA, CYD, Generic Camera/Android
```

Nie odtwarzamy obrazu z brakujących pakietów LTE. Odpytanie cache przez HTTP nie rozpoczyna połączenia P4P.

## Porty i operacje

| Port | Metoda i adres | Autoryzacja | Efekt |
| --- | --- | --- | --- |
| 8099 | GET `/`, `/status` | Tylko HA Ingress | Panel i status (token widoczny dla zalogowanego panelu). |
| 8099 | POST `/capture`, `/discover`, `/rotate-token` | Ingress | Zdjęcie, wykrywanie kamery, zmiana tokenu. |
| 8099 | POST `/framing` | Ingress | Zmiana kadru i lokalne przeliczenie. |
| 8099 | POST `/ptz` | Ingress | Ruch i nowe zdjęcie. |
| 8100 | GET `/health` | Publiczne w LAN | Stan serwera. |
| 8100 | GET `/snapshot.jpg` | Token | Źródłowe JPEG. |
| 8100 | GET `/snapshot-cyd-wide.jpg` | Token | 320×240 dla aktualnego CYD. |
| 8100 | GET `/snapshot-cyd.jpg` | Token | Starszy pionowy JPEG. |
| 8100 | GET `/snapshot-meta.json` | Token | Metadane bez haseł/UID. |
| 8100 | POST `/ptz` | **Token w nagłówku** | Tylko `left/right/up/down`. |

Odczyty GET obsługują nagłówek `X-UBox-Token` **lub** parametr URL `?token=…` (Generic Camera). JPEG zwraca `ETag` i `304 Not Modified` przy braku zmian.

Przykładowa komenda PTZ w zaufanym LAN:

~~~http
POST /ptz HTTP/1.1
Host: IP_HA:8100
X-UBox-Token: TOKEN
Content-Type: application/json

{"direction":"right"}
~~~

Odpowiedź `202` = przyjęto; `400` = nieprawidłowy kierunek; `401` = brak tokenu; `409` = zajęty; `429` = odstęp ochronny między ruchami. **To nie gwarantuje fizycznego obrotu silnika.** Kierunki i STOP mogą różnić się reakcją na różnych firmware XEGA.

**Kadrowanie** (tylko autoryzowany panel Ingress) przyjmuje:

~~~json
{"mode":"cover","focus":50}
~~~

`mode` = `blur` / `cover` / `contain`, `focus` = 0–100 (int). Po udanym przeliczeniu `last_cyd_wide.jpg` i zapisaniu `/data/framing.json` nowy ETag jest dostępny od razu; nie budzi LTE. Wariant poziomy **nie obraca** źródłowej klatki.

## LDR / jasność CYD (0.5.13 + CYD 0.2.7)

ESP32 raportuje GPIO34 (ADC1) i jasność podświetlenia co około 10 s przez `POST /brightness-telemetry` (port 8100, nagłówek tokenu, JSON `{"raw":1234,"percent":70}`). Firmware odczytuje `GET /brightness-config.json` z tokenem, otrzymuje punkty `night`/`day` i opcjonalny podgląd na 30 s. W panelu Ingress kalibracja działa przez `POST /brightness-calibrate` (`{"anchor":"night","percent":12}`) lub analogicznie `day`, próbne sterowanie przez `POST /brightness-preview` (`{"percent":12}`), reset przez `POST /brightness-reset`. Punkty przechowywane są w `/data/brightness.json`. Kalibracja **nie** wywołuje LTE. [Instrukcja](../docs/BRIGHTNESS_CALIBRATION.md).

## Pliki trwałe

| Ścieżka | Rola |
| --- | --- |
| `/data/last.jpg` | Natywny obraz HA. |
| `/data/last_cyd_wide.jpg` | Obraz 320×240 dla CYD/widgetu. |
| `/data/last_cyd.jpg` | Starsza kompatybilność. |
| `/data/last_metadata.json` | Rozdzielczość i indeks strumienia. |
| `/data/framing.json` | Wybór kadru z panelu, **ważniejszy od `config.yaml`**. |
| `/data/snapshot_token` | Sekret dla obrazów i PTZ. |

## Sterowanie PTZ

Domyślny impuls `ptz_pulse_ms: 100` i prędkość `ptz_speed: 1`, zakresy odpowiednio 60–350 ms i 1–8. IOCTRL `0x1001`: 12 bajtów; prędkość w bajcie 2, kierunek w bajcie 5, STOP = 12 zerowych bajtów. Kody: up 1, down 2, right 3, left 6. Po STOP startuje nowa sesja pobrania obrazu. Źródło mapowania: [ubox-p4p IOCTRLS](https://github.com/mahumadad/ubox-p4p/blob/main/docs/IOCTRLS.md).

## Testy / wydawanie

- `python -m unittest discover -s tests -v` — testy API i logiki.
- `python scripts/package.py` — archiwa; wymaga PyYAML.
- `pio run -d firmware/cyd_monitor` — kompilacja CYD ST7789 i ILI9341.
- GitHub Actions: [walidacja](../.github/workflows/validate.yml), [web-installer](../.github/workflows/cyd-web-installer.yml).
- Wydania eksperymentalne: [GitHub Releases](https://github.com/mpuchara/HA_UBOX_bridge/releases).

**Bezpieczeństwo:** 8100 dostępny wyłącznie w zaufanym LAN; token pozwala również ruszać kamerą. Nie wstawiaj tokenów, haseł P2P ani kont UBox do repozytorium. Aby udostępnić obraz poza domem, używaj proxy Home Assistant / VPN, nie 8100.
