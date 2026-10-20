# Instalacja i aktualizacja UBox Bridge w Home Assistant OS

**Dotyczy:** UBox Bridge **0.5.13**, Home Assistant OS **aarch64/amd64**, XEGA/UBox przez P4P. Dodatek jest eksperymentalny, nie jest oficjalnym klientem UBox.

[← README](../README.md) · [Obsługa](USER_GUIDE.md) · [CYD](CYD_WEB_INSTALL.md) · [Android](ANDROID_WIDGET.md)

## 1. Przygotuj środowisko

1. Uruchom Home Assistant **OS** z dostępem do internetu (np. Raspberry Pi 4). Repozytorium dodatków nie jest instalatorem dla HA Container/Core.
2. Sprawdź, czy kamera działa w oficjalnej aplikacji UBox i jest powiązana z kontem.
3. Zadbaj o dostęp LAN do Raspberry Pi z CYD; dodatek publikuje HTTP na **TCP 8100**. Nie przekierowuj tego portu na routerze do internetu.
4. Zdecyduj, czy logowanie będzie odbywać się przez **konto UBox** (zalecane) czy bezpośrednio przez **UID + hasło P2P**.

## 2. Dodaj repozytorium

1. Home Assistant → **Ustawienia → Dodatki / Aplikacje** (nazwy mogą różnić się między wersjami HA) → **Sklep dodatków / App Store**.
2. Menu ⋮ → **Repozytoria**, dodaj:
   `https://github.com/mpuchara/HA_UBOX_bridge`
3. Odśwież sklep, otwórz **UBox Bridge** i zainstaluj.
4. W zakładce **Konfiguracja** ustaw dane logowania i podstawowe parametry.
5. Włącz dodatek, odczytaj logi startowe, potem kliknij **Otwórz interfejs WWW** / pozycję UBox Bridge na pasku bocznym.

Gdy sklep nie pokazuje dodatku: odśwież stronę lub sprawdź, czy HA OS ma dostęp do GitHub i czy repozytorium jest prawidłowo dodane. Opcja instalacji przez ZIP jest opisana poniżej.

## 3. Minimalna konfiguracja kamery

**Wariant A — konto UBox:**
- `account_email` — e-mail konta UBox.
- `account_password` — hasło tego konta.
- `uid` — pozostaw puste, jeżeli do konta jest przypisana tylko jedna kamera. Przy kilku kamerach wskaż wybrany UID, np. odczytany po kliknięciu **Wykryj kamerę**. 
- `device_password` — zostaw puste, o ile konto dostarcza hasło urządzenia.

**Wariant B — ręczny P2P:**
- `uid` — UID urządzenia.
- `device_password` — hasło urządzenia P2P (niekoniecznie hasło konta UBox).
- Konto UBox nie jest konieczne, jeśli te dane są poprawne.

Logowanie przez Apple/Google w aplikacji UBox może nie być obsługiwane przez endpoint e-mail/hasło. Nie umieszczaj poświadczeń ani UID w issue, logach lub zrzutach ekranu. Szczegóły: [CLOUD_LOGIN.md](CLOUD_LOGIN.md).

## 4. Zalecane ustawienia

W konfiguracji graficznej dodatku ustaw:

| Opcja | Wartość startowa | Znaczenie |
| --- | --- | --- |
| `interval_minutes` | **15** w nowej instalacji | Nowa klatka co N minut; **0** wyłącza harmonogram. Kamera solarna: warto rozważyć 30–60 min. |
| `capture_on_start` | `false` | Włącz tylko, gdy chcesz wybudzać kamerę przy restarcie dodatku. |
| `video_quality` | `hd` | Prośba o HD (indeks 1); `sd` = indeks 0, `manual` korzysta z `stream_index`. |
| `stream_index` | `0` | Używany **tylko** przy `video_quality: manual`; stary zapis 0 nie blokuje domyślnego HD. |
| `live_timeout_seconds` | `45` | Czas oczekiwania klienta na wideo: 10–75 s. |
| `cyd_fit_mode` | `blur` | Wybór z listy: `blur` / `cover` / `contain`. |
| `cyd_focus_x` | `50` | Pozycja przycięcia (0–100) dla `cover`. |
| `camera_rotation` | `0` | Starsze pole zgodności; **nie obraca** aktualnego poziomego zdjęcia CYD. |
| `ptz_pulse_ms` | `100` | Czas impulsu 60–350 ms; zacznij od 100 lub 60, jeśli ruch nadal jest zbyt duży. |
| `ptz_speed` | `1` | Prędkość 1–8, 1 oznacza najwolniej. |

**Istniejące instalacje:** HA zachowuje stare zapisane opcje, także `interval_minutes: 0`. Nie zakładaj, że harmonogram zacznie działać automatycznie po aktualizacji.

**Kadrowanie:** wybór wykonany w **panelu dodatku** zapisuje się w `/data/framing.json` i **ma pierwszeństwo** przed `cyd_fit_mode` i `cyd_focus_x` z ustawień dodatku. Aby zmieniać kadr, zalecamy korzystać z listy i suwaka w panelu; nie edytuj JSON ręcznie.

## 5. Pierwsze zdjęcie i kontrola działania

1. Uruchom dodatek, otwórz jego interfejs.
2. Na górze panelu pojawi się ostatni zapisany JPEG; przy pierwszej instalacji może być pusty.
3. Pod nim wybierz **↻ Nowe zdjęcie**, poczekaj na zakończenie sesji P4P (czas zależy od kamery i LTE).
4. Sprawdź datę, rozdzielczość źródła i ewentualny komunikat błędu w sekcji zaawansowanej.
5. Wypróbuj `Blur`, `Cover`, `Contain` — przeliczają istniejący obraz, **bez ponownego połączenia LTE**.
6. Jeżeli sterowanie silnikami działa w Twoim modelu, sprawdź jeden krótki ruch PTZ. Po poleceniu bridge próbuje automatycznie odświeżyć zdjęcie.

**Gdy HD nie działa:** zmień `video_quality` na `sd`, uruchom dodatek ponownie i przetestuj zdjęcie. Żądanie HD nie gwarantuje rozdzielczości sensora.

## 6. Aktualizacja dodatku

1. Sprawdź [Releases](https://github.com/mpuchara/HA_UBOX_bridge/releases) i zanotuj działającą wersję.
2. W Home Assistant odśwież repozytorium/sklep, wybierz **UBox Bridge → Aktualizuj**, jeśli HA oferuje nową wersję.
3. Przed aktualizacją możesz zrobić kopię zapasową ustawień dodatku.
4. Po aktualizacji **uruchom ponownie dodatek**, otwórz panel i sprawdź obraz oraz stan PTZ.
5. Ustawienia w `/data` (w tym token, ostatnie zdjęcia i wybór kadrowania) powinny być zachowane przy standardowej aktualizacji.

**Kompatybilność:** Bridge 0.5.12 obsługuje **CYD 0.2.6**. Zmiany tylko w panelu HA nie wymagają ponownego wgrywania firmware na ESP32.

## 7. Instalacja ręczna z pliku ZIP (zaawansowana)

[Wydanie UBox Bridge 0.5.12](https://github.com/mpuchara/HA_UBOX_bridge/releases/tag/v0.5.12) zawiera:

- `HA-UBOX-Bridge-0.5.12-addon-root.zip` — pliki **wewnętrzne katalogu dodatku** (na poziomie głównym ma być `config.yaml`).
- `HA-UBOX-Bridge-0.5.12-repository.zip` — kompletna struktura repozytorium (katalog `ubox_bridge/`, `repository.yaml`, firmware, docs).
- `HA-UBOX-Bridge-0.5.12-complete.zip` — archiwum zbiorcze: dwie powyższe paczki i sumy SHA-256.
- `SHA256SUMS.txt` — sumy kontrolne archiwów root i repository.

W HA OS do instalacji lokalnej wymagany jest dostęp do katalogu dodatków/konfiguracji (np. SSH lub Samba). Nie wrzucaj archiwum „complete” bezpośrednio jako dodatku. Przy ręcznej instalacji rozpakuj pliki `addon-root` do katalogu dodatku, tak aby **`config.yaml` leżał bezpośrednio w katalogu dodatku**, a następnie odśwież listę lokalnych dodatków w HA. Jeżeli nie masz takiego dostępu, skorzystaj z instalacji przez repozytorium (pkt 2).

Wydania są eksperymentalne (GitHub prerelease). Zmiany dokumentacji na gałęzi `main` mogą wyprzedzać treść archiwum danej wersji.

## 8. Porty i dostęp

| Port | Po co | Autoryzacja |
| --- | --- | --- |
| `8099` | Panel wewnętrzny | Wyłącznie proxy Ingress Home Assistant; nie otwierać do LAN/WAN. |
| `8100` | Odczyt JPG i polecenia PTZ | Token lokalny UBox Bridge; tylko zaufany LAN. |
| `8123` | Standardowy interfejs HA | Kontrolowany przez Home Assistant; **nie jest** portem zdjęć CYD. |

Token znajdziesz w panelu → **Zaawansowane**. Dla CYD zwykle wpisuje się samą wartość tokenu; Generic Camera może korzystać z parametru `?token=…`. Własnych tokenów nie publikuj. Zmiana tokenu unieważni dotychczasową konfigurację CYD i Generic Camera (trzeba wprowadzić nowy).

## Następne kroki

- [Używanie UBox Bridge](USER_GUIDE.md)
- [Flashowanie i konfiguracja CYD](CYD_WEB_INSTALL.md)
- [Widżet Android i pulpit PTZ](ANDROID_WIDGET.md)
- [Błędy i diagnostyka](TROUBLESHOOTING.md)
- [Zasady bezpieczeństwa](SECURITY.md)
