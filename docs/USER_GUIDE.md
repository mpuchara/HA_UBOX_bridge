# Obsługa UBox Bridge: zdjęcia, PTZ i kadrowanie

**Aktualny zestaw:** Bridge **0.5.12**, CYD **0.2.6** (jeśli używany). Panel jest dostępny przez Home Assistant Ingress.

[← README](../README.md) · [Instalacja HA](INSTALL_HA.md) · [Android](ANDROID_WIDGET.md)

## Układ panelu — od góry

1. **Jedno duże zdjęcie 320×240**: ten sam kadr, który dostaje poziomy CYD. Zawiera znacznik czasu **ostatniego udanego** pobrania.
2. **Sterowanie kamerą PTZ**: przyciski ← ↑ ↓ → tuż pod zdjęciem. Po ruchu aplikacja wysyła STOP i rozpoczyna nowe pobranie zdjęcia.
3. **↻ Nowe zdjęcie**: ręczne wybudzenie/połączenie P4P z kamerą i aktualizacja pamięci HA.
4. **Dopasowanie kadru**: lista `Blur / Cover / Contain` oraz suwak pozycji dla `Cover`.
5. **Widżet Android i Zaawansowane**: rozwijane instrukcje, parametry strumienia, wykrywanie urządzeń, token, diagnostyka.

W panelu celowo nie ma już drugiego „oryginalnego” ani starego pionowego podglądu. Oryginalny JPEG nadal znajduje się w HA i jest dostępny przez endpoint API, ale nie zajmuje miejsca w interfejsie.

## Zdjęcie: ręcznie czy automatycznie?

| Czynność | Łączy się z kamerą LTE? | Zmienia zdjęcie? |
| --- | --- | --- |
| Wejście na panel / odświeżenie strony | **Nie** | Odczytuje istniejące |
| Sprawdzanie zdjęcia przez CYD co 30 s | **Nie** | Tylko jeśli zapisano nowy JPEG |
| Odświeżenie widżetu Android Picture | **Nie** | Pobiera istniejące przez HA |
| Wybór `Blur / Cover / Contain` | **Nie** | Tak, lokalnie przez FFmpeg |
| Przycisk **Nowe zdjęcie** | **Tak** | Po udanym pobraniu P4P |
| Harmonogram `interval_minutes > 0` | **Tak** | Gdy zaplanowany odczyt się uda |
| Ruch kamery PTZ | **Tak** | Po ruchu próba nowego zdjęcia |

Kamera solarna może reagować z opóźnieniem. Jeśli wideo nie zostanie odebrane, bridge zachowuje ostatnie poprawne zdjęcie i sygnalizuje błąd.

## Kadrowanie: wybór z listy

**Blur — domyślne:** zachowuje **cały** szeroki kadr (np. 16:9), a wolną przestrzeń nad/pod nim wypełnia rozmytą kopią tła. Żaden bok obrazu nie jest ucięty.

**Cover:** wypełnia wszystkie piksele 320×240 rzeczywistym obrazem, ale przy szerokim zdjęciu 16:9 przycina **lewy i prawy** fragment sceny. Pojawia się suwak **Pozycja kadru w poziomie 0–100%**; 50% = środek.

**Contain:** pokazuje cały obraz bez przycinania, dodając czarne pasy nad i pod zdjęciem.

Wybierz tryb z rozwijanej listy. Po krótkim przeliczeniu panel i CYD pobiorą nowy obraz. Parametry zapisywane są w `/data/framing.json` i zostają po restarcie. **Ten zapis ma pierwszeństwo** przed opcjami kadrowania w konfiguracji dodatku. Nowe zdjęcia też użyją wybranego trybu.

**Orientacja:** zdjęcie 320×240 jest przekazywane **bez obrotu kamery**. Obrót całego LCD na CYD (krótki BOOT) jest osobnym ustawieniem. Pole `camera_rotation` istnieje dla zgodności wstecznej i nie obraca tego poziomego endpointu.

## PTZ: krótkie ruchy zamiast ciągłego joysticka

- Naciśnij strzałkę w panelu albo przeciągnij palcem po CYD w wybranym kierunku.
- Bridge wysyła krótki impuls, osobne polecenie **STOP**, następnie otwiera nową sesję P4P i pobiera świeżą klatkę.
- Domyślne wartości: `ptz_pulse_ms: 100`, `ptz_speed: 1`. Jeśli obrót jest nadal za duży, zmień czas na **60 ms** w konfiguracji dodatku i zrestartuj.
- Obsługiwane kierunki: lewo / prawo / góra / dół; komendy mogą być ograniczane przez firmware kamery i stan zasilania.
- Nie nakładaj ruchów: bridge blokuje równoczesne operacje oraz ma odstęp ochronny około 5 sekund. Dotknięcie strzałki nie oznacza potwierdzenia ruchu przez silnik.

**Ważne:** fotografia to wynik nowego przechwycenia, a nie animacja w czasie rzeczywistym. Przy słabym LTE reakcja może trwać kilkanaście–kilkadziesiąt sekund. Możliwe są błędy ruchu lub STOP wynikające z nieudokumentowanego protokołu UBox.

## Ustawienia obrazu i jakości

- `video_quality: hd` żąda P4P streamIndex 1; jeśli kamera nadal daje 640×360 lub żądanie się nie powiedzie, sprawdź `sd` (index 0). Nie powiększamy obrazu sztucznie.
- W trybie `manual` działa `stream_index: 0` lub `1`; przy `hd` zapisany `stream_index: 0` jest ignorowany.
- Bridge wybiera spośród kilku kandydatów najmniej uszkodzoną klatkę, ale nie naprawi utraconych danych LTE.
- JPEG źródłowy w HA zachowuje rozdzielczość rzeczywiście dostarczoną przez kamerę; CYD zawsze otrzymuje **320×240**.

## Jak interpretować status?

**Trwa pobieranie lub przetwarzanie** — zajęty odbiór P4P, ruch PTZ albo lokalne przeliczenie kadru.

**Ostatni zapisany obraz** — data/obraz z poprzedniego udanego żądania. Nie jest to potwierdzenie, że kamera jest teraz dostępna.

**Źródło X×Y** — rozdzielczość ostatniej zapisanej klatki, nie rozdzielczość matrycy podana na pudełku.

**PTZ niedostępny / brak nowego zdjęcia** — transport nie potwierdził powodzenia albo nie uzyskano nowej klatki. Sprawdź logi i [rozwiązywanie problemów](TROUBLESHOOTING.md).

## Dalsze możliwości

- [Sterowanie przez CYD](CYD_WEB_INSTALL.md)
- [Widżet Picture i dashboard Android](ANDROID_WIDGET.md)
- [Bezpieczeństwo połączenia](SECURITY.md)
