# UBox Rożnów — Android Home Assistant Picture widget i PTZ

UBox Bridge 0.5.12+ udostępnia **ostatnie zapisane zdjęcie**, a nie stream RTSP.
Najnowszy obraz zachowuje się jak zwykła encja kamery w Home Assistant,
więc można użyć natywnego widżetu **Picture** w aplikacji Android.

## 1. Zarejestruj kamerę w Home Assistant (raz)

1. HA → **Ustawienia → Urządzenia i usługi → Dodaj integrację** → **Generic Camera**.
2. W polu **Still Image URL** wklej adres pokazany w panelu UBox Bridge
   („Widżet na telefonie”), ale **IP_HA** zamień na lokalny adres
   Raspberry Pi, np. \`192.168.1.40\`. Format:
   \`http://IP_HA:8100/snapshot-cyd-wide.jpg?token=TWÓJ_TOKEN\`.
3. **Stream Source URL** pozostaw puste — dodatek nie daje RTSP.
4. Nazwij kamerę „UBox Rożnów”. Zanotuj jej entity_id,
   np. \`camera.ubox_roznow\` (HA może nadać inne).
5. Sprawdź obraz w widoku encji kamery w Home Assistant.

HA pobiera JPEG po sieci lokalnej, a następnie udostępnia go
zalogowanym użytkownikom przez własny serwer/proxy. Dzięki temu widżet
zadziała także poza domową siecią, **jeżeli** HA jest dostępny zdalnie
(np. HA Cloud/VPN). Nie wystawiaj portu 8100 ani UBox w Internecie.

**Ważne:** token w URL działa również jako uprawnienie do wywołania PTZ,
więc traktuj go jak hasło. Nie przesyłaj zrzutów ekranu z tokenem.

## 2. Widżet na ekranie Androida

Na Samsungu: przytrzymaj wolne miejsce na ekranie głównym → Widżety →
**Home Assistant → Picture / Camera** → wybierz \`camera.ubox_roznow\`.
Jako akcję po dotknięciu wybierz **Open** (otwiera kamerę) albo
**Refresh** (ponownie pobiera JPEG z HA). Ustaw rozmiar widżetu.

Ten widget **pokazuje obraz, ale nie ma czterech strzałek PTZ**
w swoim wnętrzu. Android Picture domyślnie odświeża obraz co około godzinę
lub przy dotknięciu (nie jest to podgląd live). Jeżeli zależy Ci na
sterowaniu, dodaj poniższe cztery widżety-akcje lub skrót do dashboardu.

Oficjalna dokumentacja:
https://companion.home-assistant.io/docs/integrations/android-widgets/

## 3. (Opcjonalnie) PTZ jako natywne akcje HA

Jeżeli chcesz również przesuwać kamerę z ekranu Androida, umieść
konfigurację z \`ha-examples/ubox_android_rest_command.yaml\` w swoim
\`configuration.yaml\` (po uzgodnieniu z istniejącymi sekcjami
\`rest_command\` i \`script\`). Zmień \`IP_HA\` i wstaw sekret lokalnie,
**nie** do Git.

W \`secrets.yaml\`:

\`\`\`yaml
ubox_lan_token: "TWÓJ_TOKEN_Z_PANELU"
\`\`\`

W \`configuration.yaml\` (przykład gotowych sekcji jest w repo):

\`\`\`yaml
rest_command: !include ha-examples/ubox_android_rest_command.yaml
script: !include ha-examples/ubox_android_scripts.yaml
\`\`\`

Skopiuj pliki do \`/config/ha-examples/\` (na serwerze HA), dopasuj adres
Raspberry Pi. Nie nadpisuj całego \`script:\` albo \`rest_command:\`
jeśli już go używasz — scal istniejącą konfigurację i zrestartuj HA.

Dostaniesz skrypty \`script.ubox_lewo\`, \`script.ubox_prawo\`,
\`script.ubox_gora\` i \`script.ubox_dol\`. W Androidzie można dodać
cztery **Action button** wywołujące \`script.turn_on\` z odpowiednią encją.

Każda taka akcja wykonuje pojedynczy krótki ruch, STOP i pobiera nowe
zdjęcie tak samo jak gest na CYD. Nie przytrzymuj wielokrotnie przycisku
w krótkim czasie — kamera LTE jest wolna i ma limit ochronny.

## 4. (Opcjonalnie) Jeden ekran z obrazem i strzałkami w HA

Dodaj nowy dashboard „Kamera Rożnów”, a w widoku
**Edytuj → Dodaj kartę → Ręczny YAML** wklej
\`ha-examples/ubox_phone_cards.yaml\`. Popraw entity_id kamery, jeśli
HA nadał inne.

Na telefonie w aplikacji HA: **Ustawienia → Aplikacja towarzysząca →
Zarządzaj skrótami**. Utwórz skrót typu **Dashboard** do adresu
własnego widoku, np. \`/dashboard-roznow/0\`. Będzie to ikona, która
otwiera gotowy panel zdjęcia i sterowania. Skrót nie jest tym samym co
widżet Picture, ale pozwala sterować ze smartfona bez otwierania kolejnych
ekranów.

## 5. Kadr

W panelu UBox wybierz jednym dotknięciem \`Blur\`, \`Cover\`, \`Contain\`.
Nowa wersja JPEG zostaje wyliczona z zapisanej klatki w HA (bez LTE)
i udostępniona także Generic Camera oraz widżetowi po odświeżeniu.

Zmiana tokenu UBox spowoduje konieczność zaktualizowania URL w
Generic Camera oraz nagłówka REST w \`secrets.yaml\`.
