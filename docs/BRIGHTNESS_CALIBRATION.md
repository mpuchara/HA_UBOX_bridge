# CYD — automatyczna jasność i kalibracja fotorezystora

**Wymaga UBox Bridge 0.5.13+ i CYD firmware 0.2.7+**. Sterowanie działa na GPIO21 (PWM), a odczyt z fotorezystora na GPIO34 (ADC1). Warianty ST7789 i ILI9341 mają ten sam mechanizm. Obecność działającego LDR w konkretnym egzemplarzu wymaga sprawdzenia odczytów na urządzeniu.

[← README](../README.md) · [Instalacja CYD](CYD_WEB_INSTALL.md) · [Panel](USER_GUIDE.md)

## Dlaczego nie kalendarz zachodów słońca?

Czujnik reaguje na **rzeczywiste oświetlenie przy ekranie**, także na zachmurzenie i cień obudowy. Nie potrzebuje GPS, internetu ani poprawnej daty. Obudowa może zmniejszyć zakres odczytów, dlatego oba punkty zapisuje się **po zakończeniu montażu**.

## Kalibracja dwóch punktów krok po kroku

1. Zainstaluj **UBox Bridge 0.5.13** oraz wgraj **CYD 0.2.7** (właściwy sterownik LCD ST7789/ILI9341). Połącz CYD z Wi-Fi i HA jak dotąd.
2. Otwórz w Home Assistant panel **UBox Bridge → Automatyczna jasność CYD**. Powinieneś zobaczyć liczbowy **Odczyt LDR: 0–4095** i bieżący procent jasności LCD. Jeśli widzisz „Brak odczytu”, sprawdź firmware i sieć.
3. **W nocy**, przy docelowym oświetleniu pomieszczenia, przesuń suwak „🌙 Noc”, np. do **8–15%**. Kliknij **Wypróbuj na 30 s** i obejrzyj fizyczny ekran. Dopasuj suwak do komfortowej jasności.
4. Gdy jasność pasuje, kliknij **Zapisz noc przy obecnym pomiarze**. Bridge zapisze obecną wartość ADC oraz wybrany procent (np. `ADC 2870 → 10%`).
5. **W dzień**, przy typowym maksymalnym oświetleniu wokół docelowej obudowy, ustaw suwak „☀️ Dzień”, np. na **70–90%**. Wypróbuj, a potem wybierz **Zapisz dzień przy obecnym pomiarze** (np. `ADC 510 → 85%`).
6. Po zapisaniu obu punktów pojawi się **AUTO: aktywna interpolacja między punktami**. Od tego momentu jasność dostosowuje się lokalnie na ESP32, nawet jeśli HA jest chwilowo niedostępny.

Oba pomiary muszą się różnić o minimum **25 jednostek ADC**. Jeśli czujnik w obudowie pokazuje prawie tę samą wartość w dzień i w nocy, zasłonięty LDR może nie być użyteczny — należy zapewnić mu dopływ światła lub rozważyć inną metodę. Nie fałszujemy ręcznie pomiarów tylko po to, by włączyć AUTO.

**Wartości ADC nie mają interpretacji „większa = jaśniej”** — w wielu rewizjach CYD przy jasnym otoczeniu ADC **maleje**. Algorytm poprawnie obsługuje oba kierunki.

## Jak działa dopasowanie?

Dla przykładowej kalibracji `Noc: ADC 2870 → 10%` oraz `Dzień: ADC 510 → 85%`:

| Aktualny ADC | Jasność LCD |
| ---: | ---: |
| 2870 i wyżej | 10% |
| 2280 | ok. 29% |
| 1690 | ok. 48% |
| 1100 | ok. 66% |
| 510 i niżej | 85% |

Między punktami używana jest **interpolacja liniowa z ograniczeniem** do wartości krańcowych. ESP32 uśrednia pomiary co około 2,5 s i **płynnie zmienia PWM**, ograniczając tempo zmiany. Próbny podgląd w panelu wygasa po około 30 s; po nim wraca AUTO.

## Ograniczenia i pamięć

- **Przed zakończeniem obu kalibracji** jasność wynosi 100%, z wyjątkiem tymczasowych testów.
- Kalibracja jest przechowywana w HA: `/data/brightness.json` i kopiowana do pamięci NVS ESP32. Po restarcie i chwilowym braku HA regulacja nadal działa na zapisanych nastawach.
- Czujnik raportuje przez lokalne Wi-Fi mniej więcej co 10 s. Odczyty nie są wysyłane do kamery LTE.
- Panel HA przyjmuje komendy kalibracji **wyłącznie przez Ingress**; zewnętrzne API 8100 przyjmuje tylko telemetrię i wydaje konfigurację z prawidłowym tokenem.
- Przy bardzo małej różnicy odczytów wewnątrz obudowy AUTO może reagować na szum ADC. Jeśli tak się dzieje, wybierz jasność noc/dzień przy wyraźnie odmiennym świetle lub odsłoń okienko LDR.
- Przycisk **Usuń kalibrację jasności** czyści oba punkty w HA; po synchronizacji CYD wróci do 100% (wcześniej ostatnia konfiguracja NVS może pozostać na urządzeniu do pierwszej synchronizacji).

## Gdy pomiary nie zmieniają się

Zasłoń fotorezystor palcem, odczekaj 15–30 s, sprawdź zmianę ADC. Jeżeli stale wynosi dokładnie 0 albo 4095, być może LDR nie został zamontowany, obudowa go zasłania lub GPIO34 ma inną funkcję w tej rewizji. W takim przypadku nie można polegać na automatycznej regulacji z czujnika.

W przyszłości możemy włączyć alternatywny tryb oparty na encji Home Assistant **Sun** (wschód i zachód), ale **nie jest on jeszcze zaimplementowany** w tej wersji.
