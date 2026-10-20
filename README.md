# UBox Bridge — kamera UBox/XEGA w Home Assistant, CYD i Androidzie

**Aktualny zestaw:** UBox Bridge **0.5.12** (Home Assistant OS) + CYD Monitor **0.2.6** (ESP32-2432S028). Projekt jest eksperymentalny i nie jest oficjalną integracją UBox/XEGA.

Mostek łączy się z kamerą LTE/solarną przez P4P, przechwytuje klatkę z H.264/H.265, zapisuje **JPEG w rzeczywiście otrzymanej rozdzielczości** i przygotowuje osobny obraz **320×240** dla dotykowego CYD. Zapisane zdjęcie można wyświetlić także w aplikacji Home Assistant na Androidzie. Nie jest to ciągły podgląd na żywo.

## Rozpocznij tutaj

| Potrzebujesz… | Instrukcja |
| --- | --- |
| Instalacja / aktualizacja dodatku na Raspberry Pi z HA OS | [Instalacja Home Assistant](docs/INSTALL_HA.md) |
| Obsługa panelu, wybór kadru, zdjęcia, PTZ i ustawień | [Instrukcja obsługi](docs/USER_GUIDE.md) |
| Wgranie firmware i skonfigurowanie CYD | [Instalacja CYD przez USB](docs/CYD_WEB_INSTALL.md) |
| Widżet ze zdjęciem i sterowanie na Androidzie | [Android / Generic Camera / PTZ](docs/ANDROID_WIDGET.md) |
| Problemy z połączeniem, kadrem, dotykiem lub PTZ | [Rozwiązywanie problemów](docs/TROUBLESHOOTING.md) |
| Tokeny, dostęp LAN, bateria i prywatność | [Bezpieczeństwo](docs/SECURITY.md) |
| Zasada działania i API HTTP | [Dokumentacja techniczna](ubox_bridge/DOCS.md) |
| Wykrywanie urządzeń przez konto UBox | [Logowanie UBox](docs/CLOUD_LOGIN.md) |
| Historia wcześniejszych wersji | [Changelog](ubox_bridge/CHANGELOG.md) |

## Wymagania

- Home Assistant OS na **aarch64** (np. Raspberry Pi 4) lub **amd64**; zainstalowany dodatek UBox Bridge.
- Kamera obsługiwana przez UBox, np. **XEGA XG-01-EU4G**, z kontem UBox albo UID i hasłem urządzenia P2P. Obsługa innych modeli nie jest gwarantowana.
- Dla CYD: **ESP32-2432S028 2,8″ z XPT2046** i sprawnym Wi-Fi 2,4 GHz; do wyboru warianty LCD **ST7789** i **ILI9341**.
- Łączność sieciowa: dodatek HA → internet/P4P; CYD → Raspberry Pi na TCP **8100**; telefon → Home Assistant.

## Instalacja w skrócie

1. Dodaj repozytorium `https://github.com/mpuchara/HA_UBOX_bridge` w sklepie aplikacji/dodatków Home Assistant OS.
2. Zainstaluj **UBox Bridge 0.5.12**, uzupełnij login UBox albo dane P2P, uruchom dodatek i otwórz panel **UBox Bridge**.
3. Naciśnij **Nowe zdjęcie**. Zweryfikuj, że widoczny jest aktualny kadr oraz data ostatniego udanego pobrania.
4. Wybierz z listy **Blur / Cover / Contain**. Zmiana przelicza lokalnie zachowany JPEG i **nie budzi kamery LTE**.
5. Opcjonalnie wgraj CYD 0.2.6 przez [instalator w przeglądarce](https://mpuchara.github.io/HA_UBOX_bridge/) lub [instalator Windows ZIP](https://github.com/mpuchara/HA_UBOX_bridge/releases/tag/cyd-v0.2.6-fe27042c). Konfiguracja AP: **CYD / 12345678**; portal: `http://192.168.4.1`.
6. Opcjonalnie zarejestruj [Generic Camera](docs/ANDROID_WIDGET.md) w HA i dodaj na Androidzie widżet **Picture**.

**Pobierz aktualny dodatek:** [UBox Bridge v0.5.12](https://github.com/mpuchara/HA_UBOX_bridge/releases/tag/v0.5.12) (wydanie eksperymentalne). Dla zwykłej instalacji HA OS zalecamy sklep dodatków; dostępne pliki ZIP służą także do instalacji ręcznej i archiwizacji.

## Bieżący sposób działania

```text
Kamera XEGA/UBox (LTE, bateria słoneczna)
  └─ P4P: krótka sesja wideo na żądanie / według harmonogramu
     └─ UBox Bridge na Home Assistant OS
        ├─ /data/last.jpg             — zachowana klatka w rozdzielczości źródła
        ├─ /data/last_cyd_wide.jpg    — zdjęcie 320×240, bez obrotu kamery
        ├─ panel HA Ingress          — obraz na górze, PTZ pod nim, lista kadrowania
        └─ port 8100, LAN, token
           ├─ ESP32 CYD              — ekran i gesty PTZ
           └─ Generic Camera → HA → widżet Picture w Androidzie
```

**Fotografia a sterowanie:** CYD oraz widżet Androida czytają plik z pamięci HA. Samo odświeżenie tego pliku przez HTTP **nie** łączy się z LTE. Nowa transmisja pojawia się dopiero po ręcznym pobraniu, automatycznym harmonogramie lub po poleceniu ruchu PTZ.

**PTZ (eksperymentalnie):** krótkie polecenia lewo/prawo/góra/dół, zatrzymanie i próba pobrania nowego zdjęcia. Domyślny impuls **100 ms**, prędkość **1**, regulacja w ustawieniach dodatku. Fizyczne zachowanie zależy od firmware kamery.

## Ważne ograniczenia

- `video_quality: hd` **żąda** strumienia HD, ale nie gwarantuje jego rozdzielczości. Panel pokazuje rzeczywistą rozdzielczość zapisanej klatki.
- Nie ma RTSP, nagrywania ciągłego ani potwierdzonego sterowania trybem IR/białych LED.
- CYD używa w poziomie **320×240** i domyślnie ma złącza USB po prawej w dolnej części; krótkim BOOT można obrócić interfejs o 180°.
- Hasło AP `12345678` jest świadomie proste i **słabe**. Używaj go wyłącznie w zaufanym otoczeniu do wstępnej konfiguracji.
- Token z panelu daje dostęp **zarówno do zdjęć, jak i do PTZ**. Nie publikuj go, nie otwieraj portu 8100 na WAN i nie umieszczaj tokenu w repozytorium.

## Rozwój i źródła

Backend bazuje na przypiętej wersji [asyrk/ubox-web](https://github.com/asyrk/ubox-web), korzysta z FFmpeg/FFprobe i jest w fazie testów. Dodatkowe informacje o protokole oraz strukturze projektu są w [DOCS](ubox_bridge/DOCS.md). Wydanie firmware i dokumentacja są dostępne w tym repozytorium; pliki użytkowników, tokeny i hasła nie są przechowywane w Git.
