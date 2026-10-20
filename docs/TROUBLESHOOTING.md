# Rozwiązywanie problemów — UBox Bridge 0.5.13 / CYD 0.2.7

[← README](../README.md) · [Instalacja HA](INSTALL_HA.md) · [Instalacja CYD](CYD_WEB_INSTALL.md) · [Bezpieczeństwo](SECURITY.md)

## Szybka diagnostyka — od czego zacząć?

1. Czy **górne zdjęcie w panelu UBox Bridge** jest prawidłowe?
2. Czy pokazuje poprawną datę ostatniego pobrania? To **obraz z pamięci HA**, nie live.
3. Czy w sekcji **Zaawansowane** występuje błąd P4P, kod HTTP, czy informacja o rozdzielczości?
4. Jeżeli tylko CYD jest uszkodzony, uruchom go ponownie i obejrzyj test czterech kolorów.
5. Jeśli problem dotyczy Androida, najpierw sprawdź obraz w encji **Generic Camera** wewnątrz HA.

## A. Dodatek nie pojawia się w sklepie Home Assistant

Upewnij się, że masz **Home Assistant OS** oraz dodane repo `https://github.com/mpuchara/HA_UBOX_bridge`. Odśwież sklep aplikacji/dodatków i sprawdź dostęp hosta do GitHub. Nie instaluj ZIP „complete” jako pojedynczego dodatku — struktura katalogów jest inna. Zobacz [INSTALL_HA.md](INSTALL_HA.md).

## B. Brak kamery / logowanie do UBox

Sprawdź konto e-mail/hasło lub prawidłową parę UID + hasło P2P. Przy kilku urządzeniach wskaż wybrany UID. Logowanie federacyjne Google/Apple może nie odpowiadać API e-mail/hasło. Przy problemach po stronie chmury UBox konieczne może być użycie ręcznych danych P2P.

Nie udostępniaj hasła, UID ani pełnych logów bez wcześniejszego usunięcia sekretów. [Dokumentacja odkrywania urządzeń](CLOUD_LOGIN.md).

## C. `video_quality: hd` nadal daje 640×360

`hd` żąda strumienia nr 1, lecz **nie wymusza rozdzielczości fizycznego sensora**. Źródłem może być profil w firmware kamery, ograniczenie sieci LTE albo działanie P4P. W panelu podana jest **rzeczywiście zapisana** rozdzielczość, a nie rozdzielczość reklamowana.

Spróbuj pojedynczego zdjęcia w `hd`, a jeśli nie działa, przełącz na `sd` i ponownie uruchom dodatek. Nie ustawiaj bardzo krótkich harmonogramów, aby nie rozładować kamery solarnej.

## D. Zdjęcie zawiera zielone pasy / „śnieg” / porwane fragmenty

- **Pasy są w panelu HA:** zwykle problem dekodowania lub niekompletna transmisja P4P. Bridge wybiera mniej uszkodzoną klatkę, ale nie odtworzy utraconych fragmentów. Zrób kolejne zdjęcie przy lepszej łączności.
- **Panel HA jest czysty, a CYD ma pasy:** problem wyświetlacza/sterownika/SPI. Wgraj właściwy wariant **ST7789** albo **ILI9341**, zweryfikuj napięcie zasilania i test czterech kolorów. Gdy obraz testowy jest wadliwy, nie szukaj przyczyny w JPEG z kamery.
- **Stary fragment nie znika:** sprawdź, czy CYD aktualnie używa firmware **0.2.6**, czy odczytuje `/snapshot-cyd-wide.jpg` i czy nie ma błędów HTTP/JPEG. Dodatek zachowuje poprzednie zdjęcie w przypadku nieudanej nowej transmisji.

## E. Obraz do góry nogami / w bok / nie wypełnia LCD

- Krótko naciśnij **BOOT** na działającym CYD, aby przełączyć obrót LCD o **180°**.
- Bridge 0.5.12 przekazuje poziomy JPEG **bez obrotu klatki kamery**. Stare instrukcje o wymuszonym 90° dotyczą nieaktualnych wersji.
- Jeśli chcesz zachować całą scenę 16:9, wybierz **Blur** lub **Contain**. Jeśli chcesz obraz na całym LCD bez pasów, wybierz **Cover** i ewentualnie ustaw kadr suwakiem.
- Jeśli wybranie trybu nie zmienia obrazu, upewnij się, że istnieje poprawny zapisany JPEG w HA i że operacja nie trwa równocześnie z pobieraniem.

## F. CYD nie łączy się z Wi-Fi / nie pobiera obrazu

- Portal pierwszej konfiguracji: Wi-Fi **CYD**, hasło **12345678**, strona **`http://192.168.4.1`**.
- Domowe Wi-Fi musi obsługiwać **2,4 GHz**, a Raspberry Pi i CYD muszą mieć wzajemną trasę w LAN. Sieć gościnna/izolacja klientów może blokować TCP **8100**.
- Host w konfiguracji CYD: wyłącznie adres IP, **bez** `http://` i **bez** `:8123`. Token: wyłącznie wartość tokenu.
- Port `8100` musi być opublikowany w ustawieniach dodatku. Nie wystawiaj go w internecie.
- Po rotacji tokenu w HA wpisz nowy token także na CYD.
- Przytrzymaj BOOT ≥5 sekund podczas normalnej pracy, by ponownie uruchomić konfigurator (usunie zapisane Wi-Fi/host/token).

## G. Dotyk nie reaguje / kierunki są odwrócone

- Ponowna kalibracja **BOOT 2,1–4,9 s**; dotknij kolejno trzech krzyżyków.
- Jeżeli dotyk nie był skalibrowany przy pierwszym starcie, wyświetlacz nadal pokazuje zdjęcie, ale gesty są nieaktywne.
- Zwróć uwagę na fizyczną orientację LCD i krótki BOOT (obrót o 180°).
- Przy nieprawidłowych kierunkach ruchu sprawdź najpierw działanie przycisków **PTZ w panelu HA**. Jeśli tam również kierunki są złe, problem jest po stronie protokołu kamery, a nie mapowania dotyku.

## H. PTZ kręci tylko w jedną stronę / robi duże ruchy

W wersjach przed **0.5.11** istniał błąd pakietu sterowania. Zaktualizuj mostek do **0.5.12**. Domyślny impuls to **100 ms / speed 1**, z oddzielnym STOP. Przy zbyt dużym ruchu ustaw `ptz_pulse_ms: 60`, `ptz_speed: 1`.

Urządzenie jest solarne i komunikuje się po LTE, więc opóźnienia poleceń oraz brak gwarancji wykonania STOP zależą także od firmware kamery. Po nieudanej próbie **nie wysyłaj wielu kolejnych ruchów**. Sprawdź status PTZ i logi w HA.

## I. Widget Android Picture jest pusty lub nie odświeża się

1. Otwórz w HA encję `camera.ubox_roznow`. Jeśli tu nie ma zdjęcia — popraw URL i token Generic Camera.
2. Sprawdź, czy HA host potrafi po LAN pobrać HTTP z `IP_HA:8100`.
3. Widżet **Picture** nie pokazuje live. Standardowo odświeża się **co godzinę** lub po dotknięciu (jeśli wybierzesz Refresh).
4. Skontroluj uprawnienia Home Assistant Companion do działania w tle, transmisji danych i oszczędzania baterii; w razie potrzeby utwórz widżet ponownie.
5. Po zmianie tokenu zaktualizuj URL encji Generic Camera i sekret dla akcji PTZ.

[Android — pełna instrukcja](ANDROID_WIDGET.md).

## J. Czujnik jasności nie działa po włożeniu w obudowę

W panelu powinien być widoczny odczyt **LDR (0–4095)**. Jeśli go nie ma, sprawdź, czy wgrałeś CYD 0.2.7, token i Wi-Fi. Jeżeli odczyt niemal się nie zmienia między dniem a nocą, osłona może zasłaniać czujnik; minimum rozróżnialności do kalibracji to 25 jednostek ADC. Sprawdź czujnik pod światłem i po zasłonięciu palcem. Warianty CYD mogą różnić się obsadzeniem elementów. Szczegóły: [Kalibracja jasności](BRIGHTNESS_CALIBRATION.md).

## K. Jak bezpiecznie zgłaszać błąd

Podaj **wersję Bridge**, **wersję CYD**, wariant LCD (ST7789/ILI9341), **model kamery**, wybrany tryb HD/SD, opis ostatniej czynności i datę zdjęcia. Dołącz zdjęcie ekranu testowego LCD lub skadrowany fragment diagnostyki **po usunięciu** UID, adresu konta, hasła i tokenu.

Nie publikuj całych URL z `?token=…`, danych logowania UBox ani pełnego zrzutu konfiguracji dodatku.
