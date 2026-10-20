# Logowanie i wykrywanie kamery UBox

[← README](../README.md) · [Instalacja HA](INSTALL_HA.md) · [Problemy](TROUBLESHOOTING.md)

W panelu konfiguracyjnym UBox Bridge dostępne są dwie metody połączenia:

1. **Konto UBox** — `account_email` + `account_password`. Przy jednej kamerze dodatek może wybrać ją samodzielnie. Przy wielu wpisz dodatkowo `uid` wybranego urządzenia.
2. **Ręczny P2P** — `uid` + `device_password`. Hasło urządzenia nie musi być identyczne z hasłem konta UBox.

Przycisk **Wykryj kamerę** korzysta z nieoficjalnie udokumentowanych endpointów chmury:
- `POST https://portal.ubianet.com/api/v3/login` — uwierzytelnienie konta.
- `POST https://portal.ubianet.com/api/v2/user/device_list` — lista przypisanych urządzeń.

Nie jest to oficjalne SDK. Logowanie przez Google/Apple w aplikacji UBox może nie działać poprzez ten formularz e-mail/hasło. Loginy i hasła zapisane są lokalnie w konfiguracji dodatku HA; panel statusu nie zwraca ich publicznie. HTTPS weryfikuje certyfikat.

Samo odkrycie urządzenia **nie oznacza jeszcze sukcesu odbioru wideo**. Właściwe zdjęcie wymaga nawiązania sesji P4P przez bibliotekę ubox-web. Obsługa XEGA XG-01-EU4G była testowana w projekcie, ale inne rewizje firmware i zmiany serwerów chmurowych nie są gwarantowane.

**Rozwiązywanie problemów:** sprawdź, czy aplikacja UBox loguje się na konto, czy kamera jest przypisana do tego konta, czy wpisano prawidłowy UID (w razie wielu kamer) i czy HA ma internet. Gdy chmura nie obsługuje sposobu logowania, rozważ ręczny UID+hasło P2P.

**Bezpieczeństwo:** nie publikuj kont, haseł, UID, tokenu snapshotów ani pełnych adresów `?token=…`. Token UBox Bridge to osobny sekret — służy do pobierania zdjęć i sterowania PTZ.
