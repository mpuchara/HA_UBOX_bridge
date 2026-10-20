# Android — widżet zdjęcia UBox i sterowanie kamerą w Home Assistant

Dotyczy **UBox Bridge 0.5.12+** oraz aplikacji **Home Assistant Companion na Androidzie**. Zamiast budować dodatkową apkę, wykorzystujemy natywną encję **Generic Camera**, widżet **Picture** i opcjonalne skrypty PTZ. Nie potrzebujesz osobnej aplikacji UBox do wyświetlania zdjęcia z bridge’a.

[← README](../README.md) · [Instalacja dodatku](INSTALL_HA.md) · [Panel](USER_GUIDE.md)

## Co jest możliwe, a co nie?

| Funkcja | Android Picture | Dashboard w HA |
| --- | --- | --- |
| Ostatnie zapisane zdjęcie | **Tak** | **Tak** |
| Odświeżenie istniejącego JPEG | **Tak** — działanie Refresh | Tak, przy odświeżeniu encji |
| Strzałki PTZ na tym samym widżecie | **Nie** | **Tak**, jako przyciski poniżej zdjęcia |
| PTZ z osobnych widżetów akcji | **Tak**, osobne Action button | Tak |
| Wideo na żywo | **Nie** | **Nie** — bridge zapisuje pojedyncze klatki |
| Nowa sesja LTE po dotknięciu Refresh | **Nie** | Nie, chyba że osobno wywołasz Nowe zdjęcie/PTZ |

**Uwaga:** oficjalny widżet Picture aktualizuje obraz zwykle **co godzinę** lub po dotknięciu (zależnie od wybranej akcji), zgodnie z [dokumentacją Companion](https://companion.home-assistant.io/docs/integrations/android-widgets/). Częstość odświeżania widżetu jest niezależna od harmonogramu pobierania zdjęć z kamery.

## Krok 1. Utwórz encję Generic Camera (jednorazowo)

1. W Home Assistant wybierz **Ustawienia → Urządzenia i usługi → Dodaj integrację → Generic Camera**.
2. W panelu dodatku UBox Bridge rozwiń **Widżet na telefonie z Home Assistant**. Skopiuj adres zdjęcia.
3. Zastąp w nim `IP_HA` prawdziwym lokalnym IP Raspberry Pi (bez nawiasów i bez portu HA 8123), np.:
   `http://192.168.1.40:8100/snapshot-cyd-wide.jpg?token=TWÓJ_TOKEN`
4. Jako **Still Image URL** wpisz ten adres. **Stream Source URL** zostaw puste — bridge nie daje RTSP.
5. Jeśli konfigurator ma opcję `Verify SSL` i zgłasza problem dla HTTP, użyj ustawienia odpowiedniego dla lokalnego HTTP, zgodnie z [Generic Camera](https://www.home-assistant.io/integrations/generic).
6. Nazwij urządzenie „UBox Rożnów” i zapamiętaj identyfikator encji, np. `camera.ubox_roznow` (w Twoim HA może być inny).
7. Sprawdź, czy encja pokazuje kadr także po ponownym uruchomieniu HA.

**Dlaczego to jest bezpieczniejsze?** Home Assistant pobiera obraz z bridge’a po LAN i udostępnia go zalogowanym użytkownikom przez własny proxy (`/api/camera_proxy/...`). Dostęp zdalny powinien odbywać się przez HA Cloud lub własny VPN, **bez otwierania TCP 8100 na routerze**.

**Ostrożnie z tokenem:** pełny URL kamery zawiera sekret UBox Bridge. Ustawienia Generic Camera zapisuj tylko w HA; nie wstawiaj prawdziwego tokenu do publicznego repozytorium ani na zrzuty ekranu.

## Krok 2. Dodaj widżet Picture na Androidzie

1. Na telefonie przytrzymaj puste miejsce na ekranie startowym.
2. **Widżety → Home Assistant → Picture** (w niektórych tłumaczeniach „Kamera”).
3. Wybierz encję `camera.ubox_roznow` albo swój odpowiednik.
4. Ustaw reakcję na dotknięcie: **Refresh** (odśwież obraz) lub **Open** (otwórz ekran encji kamery).
5. Ustaw rozmiar widżetu, zatwierdź.

Jeżeli widżet nie odświeża się, sprawdź uprawnienia pracy w tle i wyłącz dla HA ograniczenia oszczędzania danych; w razie potrzeby usuń widżet i utwórz go ponownie. Szczegóły odświeżania zależą od systemu Android i ustawień aplikacji.

## Krok 3. (Opcjonalnie) Cztery akcje PTZ jako skrypty HA

W repo znajdują się gotowe **przykłady**, które trzeba ręcznie wprowadzić do konfiguracji Home Assistant:

- [REST-command z tokenem w nagłówku](../ha-examples/ubox_android_rest_command.yaml)
- [Cztery skrypty ruchu](../ha-examples/ubox_android_scripts.yaml)
- [Karta dashboardu: zdjęcie i 4 przyciski](../ha-examples/ubox_phone_cards.yaml)

1. Skopiuj pierwsze dwa pliki do katalogu `/config/ha-examples/` na swoim HA.
2. W pliku `ha-examples/ubox_android_rest_command.yaml` zmień **przykładowy adres 192.168.1.40** na adres własnego Raspberry Pi.
3. Dodaj do **`/config/secrets.yaml`** sekretny nagłówek:

   ~~~yaml
   ubox_lan_token: "TWÓJ_TOKEN_Z_PANELU"
   ~~~

4. Jeżeli Twoje `configuration.yaml` **nie ma** sekcji `rest_command` i `script`, możesz użyć:

   ~~~yaml
   rest_command: !include ha-examples/ubox_android_rest_command.yaml
   script: !include ha-examples/ubox_android_scripts.yaml
   ~~~

   Jeśli masz już te sekcje lub własne skrypty, **nie zastępuj ich**. Scal zawartość plików z dotychczasowymi definicjami w odpowiednich sekcjach.

5. Sprawdź poprawność konfiguracji HA, przeładuj REST commands / skrypty (jeśli obsługiwane), ewentualnie uruchom HA ponownie.
6. Przetestuj `script.ubox_lewo` w **Narzędzia deweloperskie → Akcje**. Ma wykonać pojedynczy krótki ruch, STOP i zainicjować nową klatkę. Pamiętaj, że fizyczny PTZ przez P4P jest eksperymentalny.

**Wariant bez edycji YAML:** możesz korzystać ze strzałek już w panelu dodatku UBox Bridge w aplikacji HA, otwierając jego Ingress. Skrypty są potrzebne dopiero dla dodatkowych przycisków HA/widgetów akcji.

## Krok 4. (Opcjonalnie) Widżety Action button lub dashboard telefonu

**Cztery widżety:** dodaj **Home Assistant → Action button** dla akcji `script.turn_on` i odpowiedniej encji `script.ubox_lewo` / `script.ubox_prawo` / `script.ubox_gora` / `script.ubox_dol`. Każde naciśnięcie otwiera osobną sesję PTZ; zachowuj odstęp między ruchami.

**Jeden ekran w HA:** dodaj do dashboardu kartę **Ręczny YAML** z zawartością [ubox_phone_cards.yaml](../ha-examples/ubox_phone_cards.yaml). Zamień `camera.ubox_roznow`, jeśli identyfikator jest inny. Na telefonie utwórz skrót do tego dashboardu lub dodaj go do ulubionych w aplikacji HA.

**Ograniczenie:** standardowy Android Picture nie potrafi wstawić czterech przycisków na środek zdjęcia. Przełączaj się do panelu/dashboardu, gdy potrzebujesz PTZ.

## Krok 5. Zmiana kadru albo tokenu

- Wybranie w panelu **Blur / Cover / Contain** zmienia JPEG 320×240, który odczytuje także encja Generic Camera. Wystarczy odświeżyć widżet, **bez nowej transmisji LTE**.
- Gdy w panelu użyjesz **Wygeneruj nowy token**, dotychczasowy URL i żądania PTZ przestaną działać. Uaktualnij **Generic Camera**, `secrets.yaml` oraz konfigurację CYD (jeśli używane).

[Oficjalna dokumentacja widżetów Android](https://companion.home-assistant.io/docs/integrations/android-widgets/) · [Generic Camera](https://www.home-assistant.io/integrations/generic) · [RESTful Command](https://www.home-assistant.io/integrations/rest_command/).
