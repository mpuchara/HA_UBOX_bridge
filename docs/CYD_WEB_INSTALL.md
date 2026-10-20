# CYD ESP32-2432S028 — instalacja, połączenie i gesty PTZ

**Aktualny firmware: 0.2.7** · **Wymaga UBox Bridge 0.5.13 dla regulacji jasności**.

[← README](../README.md) · [Instalacja HA](INSTALL_HA.md) · [Obsługa](USER_GUIDE.md) · [Rozwiązywanie problemów](TROUBLESHOOTING.md)

## 1. Czy moja płytka jest obsługiwana?

Firmware przygotowano dla **klasycznego ESP32-2432S028 2,8 cala / 240×320** z panelem oporowym **XPT2046**. Działa w orientacji **poziomej 320×240**, z USB w okolicy **prawego dolnego rogu** po docelowym zamontowaniu.

| Wariant LCD | Kiedy wybrać |
| --- | --- |
| **ST7789** | Pierwszy test na płytce z dwoma gniazdami USB (USB-C i micro-USB); na tej odmianie obraz działał poprawnie. |
| **ILI9341** | Alternatywa, gdy test kolorów lub wyświetlanie ST7789 jest niepoprawne. |

Model i rozstaw pinów są ważniejsze niż sam wygląd płytki. **Nie flashuj** tego obrazu na ESP32-S3, ESP32-P4 ani na innych niezgodnych wersjach CYD. Jeśli po uruchomieniu widać pasy, niekompletny obraz lub dziwne kolory, wypróbuj drugi wariant sterownika.

## 2. Co przygotować przed wgraniem

- Home Assistant OS z działającym **UBox Bridge 0.5.12**.
- W panelu dodatku **Zaawansowane** odczytaj token UBox Bridge. Nie kopiuj go do publicznych zgłoszeń ani na zrzuty ekranu.
- Znaj adres IP **Raspberry Pi / hosta HA** w LAN, np. `192.168.1.40` (bez `http://` i bez `:8123`).
- Dostęp do domowego Wi-Fi **2,4 GHz**, z którego CYD osiągnie port TCP **8100** Raspberry Pi.
- Komputer z Chrome/Edge i przewód USB z transmisją danych (nie wyłącznie do ładowania).

## 3. Wgrywanie firmware z przeglądarki — zalecane

**Instalator:** https://mpuchara.github.io/HA_UBOX_bridge/

1. Podłącz CYD przez USB do komputera Windows. Port może być **COM4**, ale nie zakładaj stałego numeru.
2. Otwórz instalator w aktualnym **Chrome** lub **Edge** z obsługą Web Serial.
3. Kliknij **ST7789**, jeżeli masz tę samą dwuportową płytkę; jeśli obraz nie działa poprawnie, wybierz **ILI9341**.
4. Wybierz rozpoznany port COM, zaakceptuj instalację i zaczekaj na koniec flashowania.
5. Po uruchomieniu sprawdź cztery pola testowe: czerwone, zielone, niebieskie i białe. Nie powinno być pasków ani fragmentów starego obrazu.
6. Skonfiguruj Wi-Fi i token zgodnie z krokiem 5 poniżej.

**Uwaga:** pierwsza instalacja lub wybór kasowania może wyczyścić pamięć flash i zapisane Wi-Fi/token. Gdy instalator Web Serial nie działa, sprawdź kabel, sterowniki USB, inne aplikacje używające COM oraz [diagnostykę](TROUBLESHOOTING.md).

Jeśli GitHub Pages nie jest aktywne: repozytorium → **Settings → Pages → Source: GitHub Actions**; następnie workflow [Build and publish CYD browser installer](../.github/workflows/cyd-web-installer.yml).

## 4. Alternatywa: instalator Windows ZIP (bez PlatformIO)

[Pobierz wersję CYD 0.2.6 dla Windows](https://github.com/mpuchara/HA_UBOX_bridge/releases/tag/cyd-v0.2.6-fe27042c) → `UBox-CYD-Windows-Browser-Installer.zip`.

1. **Wypakuj** całe archiwum do folderu, nie uruchamiaj skryptu z podglądu ZIP.
2. Uruchom `Start-Installer.cmd`. Otworzy się lokalny serwer HTTP na `127.0.0.1` i przeglądarka.
3. Wybierz sterownik ST7789 albo ILI9341, wskaż odpowiedni port i flashuj.
4. Nie zamykaj okna z serwerem do zakończenia instalacji.

Instalator nie potrzebuje Pythona ani PlatformIO na komputerze. Do załadowania ESP Web Tools wymagane jest połączenie przeglądarki z internetem. [Szczegóły Windows](../windows-installer/README.md).

## 5. Pierwsze połączenie CYD z Home Assistant

1. Jeśli CYD nie ma zapisanej konfiguracji, wystawi AP: **SSID `CYD`, hasło `12345678`**.
2. Połącz telefon/komputer z `CYD`. Brak internetu w tym Wi-Fi jest normalny. Jeśli telefon sam przełącza się z powrotem na LTE, wybierz „Pozostań połączony”.
3. Otwórz w przeglądarce **`http://192.168.4.1`**, jeśli kreator nie pojawi się automatycznie.
4. Wybierz domowe Wi-Fi **2,4 GHz** i wpisz hasło.
5. W polu adresu Raspberry Pi podaj sam adres IP (np. `192.168.1.40`), **bez** `http://`, `:8100` i `:8123`.
6. W pole tokenu wklej **sam token** z panelu UBox Bridge → Zaawansowane, **nie pełny adres URL**.
7. Zapisz. CYD połączy się z domową siecią i pobierze `/snapshot-cyd-wide.jpg`.

Hasło AP jest celowo proste, ale niebezpieczne w publicznym otoczeniu — korzystaj z kreatora krótko, w domu, a po konfiguracji wyłącz punkt dostępowy przez połączenie do domowego Wi-Fi.

## 6. Obsługa na ekranie

**Zwykły tryb**: CYD wyświetla ostatni 320×240 JPEG z HA; standardowo sprawdza nowy obraz co **30 s** (ETag/304), nie zużywając transferu LTE na samo sprawdzenie.

**PTZ gestami:** przeciągnij palcem poziomo/pionowo po obrazie (co najmniej ok. **38 px**). Jedno przeciągnięcie wysyła **jedno** polecenie lewo/prawo/góra/dół do UBox Bridge, który wysyła STOP i próbuje uzyskać nowe zdjęcie. Po geście CYD sprawdza nowy obraz co około **2,5 s**, maksymalnie przez **110 s**.

**Kalibracja dotyku:** przy pierwszym uruchomieniu pojawią się **trzy żółte krzyżyki**. Dotknij ich kolejno. Kalibracja zostaje zapisana w pamięci. Jeśli czas minie bez dotyku, monitor uruchomi się, ale **gesty nie zadziałają** do ponownej kalibracji.

| BOOT podczas normalnej pracy | Działanie |
| --- | --- |
| Krótko (ok. 0,1–1,8 s) | Obrót całego LCD o 180°; zapamiętuje ustawienie. |
| Przytrzymanie **2,1–4,9 s** | Ponowna kalibracja XPT2046. |
| Przytrzymanie **≥5 s** | Usunięcie ustawień Wi-Fi/hosta/tokenu i ponowna konfiguracja. |

Nie przytrzymuj BOOT **podczas resetu/włączania** — może to wprowadzić ESP32 w tryb programowania.

**Wielkość kroku PTZ** ustawiasz w konfiguracji **dodatku HA**, nie w firmware CYD:
`ptz_pulse_ms: 100` oraz `ptz_speed: 1` (60–350 ms i 1–8). Dla zbyt dużych ruchów użyj 60 ms.

## 7. Gdy CYD nie aktualizuje obrazu

Sprawdź po kolei:
1. Czy w panelu dodatku HA aktualizuje się **górne zdjęcie**?
2. Czy host wpisany w CYD jest adresem IP Raspberry Pi, a TCP **8100** jest osiągalny?
3. Czy token się nie zmienił (rotacja tokenu wymaga ponownej konfiguracji CYD)?
4. Czy masz ten sam sterownik ekranu ST7789/ILI9341, na którym wcześniej działały testowe kolory?
5. Czy na HA istnieje `last_cyd_wide.jpg` (po pierwszym udanym zrzucie)?

Szczegóły: [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## 8. Kalibracja automatycznej jasności

Po umieszczeniu płytki w docelowej obudowie otwórz panel UBox Bridge → **Automatyczna jasność CYD**. Sprawdź odczyt ADC z GPIO34, wybierz suwakiem jasność „Noc”, użyj przycisku **Wypróbuj**, a potem **Zapisz noc przy obecnym pomiarze**. W dzień powtórz dla punktu „Dzień”. Po zapisie dwóch różnych odczytów ESP32 interpoluje poziom podświetlenia między nimi (PWM GPIO21). Pełna instrukcja: [Kalibracja jasności](BRIGHTNESS_CALIBRATION.md).

## 9. Bezpieczeństwo

Portal Wi-Fi pod `192.168.4.1` nie przekazuje poświadczeń do witryny GitHub Pages. Dane Wi-Fi i token są zapisywane lokalnie w NVS ESP32. Token UBox Bridge **pozwala również wykonywać ruchy PTZ** przez LAN — traktuj go jak hasło, nie publikuj zdjęć zawierających token i **nie wystawiaj portu 8100 na internet**.
