# Neolink dla Home Assistant

🇬🇧 [English version](README.md)

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/docs/faq/custom_repositories)

Integracja Home Assistant dla **kamer Reolink bateryjnych i 4G, które nie mają lokalnego API**,
takich jak Reolink Go Plus czy Go G330. Tych kamer nie da się dodać wbudowaną integracją Reolink.
Ta integracja komunikuje się z nimi przez
[Neolink](https://github.com/QuantumEntangledAndy/neolink), korzystając z forka z API WebSocket,
który działa jako aplikacja (dodatek) **Neolink**:
[home-assistant-neolink-addon](https://github.com/witold-gren/home-assistant-neolink-addon).

MQTT nie jest potrzebne. Stan jest przesyłany przez jedno połączenie WebSocket, a integracja jest
zbudowana tak, aby kamera bateryjna była budzona tylko wtedy, gdy naprawdę o coś prosisz.

```
Reolink camera ──Baichuan (LAN / P2P / 4G)──► Neolink app ──WebSocket──► neolink integration ──► entities
                                               │  └─ RTSP ──► go2rtc / stream ──► live view
                                               └─ Supervisor discovery ──► "Discovered: Neolink"
```

## Wymagania

- Home Assistant 2026.2 lub nowszy.
- Aplikacja **Neolink** z
  [home-assistant-neolink-addon](https://github.com/witold-gren/home-assistant-neolink-addon),
  zainstalowana, skonfigurowana z Twoimi kamerami i uruchomiona. Bez Supervisora (na przykład
  w Home Assistant Container) możesz samodzielnie uruchomić ten sam fork Neolink i dodać go ręcznie.
- Do podglądu na żywo: integracja `stream` lub go2rtc (obie są częścią domyślnej konfiguracji).

## Instalacja

### HACS (zalecane)

1. W HACS otwórz menu (trzy kropki) → **Niestandardowe repozytoria**.
2. Dodaj `https://github.com/witold-gren/home-assistant-neolink-integration` z kategorią
   **Integracja**.
3. Wyszukaj **Neolink**, pobierz i uruchom ponownie Home Assistant.

### Ręcznie

Skopiuj `custom_components/neolink` z tego repozytorium do `custom_components/neolink` w katalogu
konfiguracji Home Assistant i uruchom ponownie Home Assistant.

## Konfiguracja

### Automatyczne wykrywanie

Gdy aplikacja Neolink działa, Supervisor zgłasza ją do Home Assistant. Przejdź do
**Ustawienia → Urządzenia i usługi**; pojawi się tam wykryty **Neolink**. Potwierdź i gotowe:
adres, porty, token i dane logowania RTSP pochodzą z aplikacji.

Jeśli aplikacja uruchomi się ponownie z nowym adresem lub tokenem, istniejący wpis zostanie
zaktualizowany automatycznie. Jeśli przeinstalujesz aplikację (na przykład zastąpisz lokalną kopię
wersją ze sklepu), nowa instalacja przejmie istniejący wpis, więc Twoje urządzenia i identyfikatory
encji pozostaną bez zmian.

### Konfiguracja ręczna

**Ustawienia → Urządzenia i usługi → Dodaj integrację → Neolink**, a następnie wypełnij:

| Pole | Opis |
|---|---|
| Host | Adres mostu Neolink. |
| Port WebSocket | Port API WebSocket (domyślnie `3002`). |
| Token | Token API skonfigurowany w moście; zostaw puste, jeśli go nie ma. |
| Port RTSP | Port serwera RTSP mostu (domyślnie `8554`). |
| Nazwa użytkownika / hasło RTSP | Dane logowania RTSP, jeśli most ich wymaga. |

## Encje

Każda kamera skonfigurowana w aplikacji staje się urządzeniem. Encje są tworzone tylko dla funkcji,
które zgłaszają kamera i most.

| Encja | Typ | Uwagi |
|---|---|---|
| Kamera | camera | Podgląd na żywo z serwera RTSP mostu; obraz statyczny pochodzi wyłącznie z pamięci podręcznej mostu. |
| Ostatnie zdjęcie, Ostatnie zdarzenie | image | Z pamięci podręcznej mostu. *Ostatnie zdarzenie* to zdjęcie zrobione po powiadomieniu o ruchu. |
| Bateria | sensor | Poziom baterii w %. |
| Temperatura baterii, Napięcie baterii | sensor | Diagnostyczne; napięcie jest domyślnie wyłączone. |
| Ostatni ruch | sensor | Czas ostatniego powiadomienia push o ruchu. |
| Ostatnie wykrycie | sensor | Co wywołało ostatnie powiadomienie: osoba, pojazd, zwierzę, ruch lub inne. |
| Ostatnie zdjęcie | sensor | Czas zdjęcia w pamięci podręcznej (diagnostyczny). |
| Karta pamięci zajęta, Karta pamięci wolne, Karta pamięci pojemność | sensor | Odczytywane, gdy kamera się łączy; nieznane, gdy karta nie jest zamontowana. |
| Sygnał 4G, Sygnał 4G (wartość), Operator | sensor | Tylko kamery 4G; wartość sygnału jest domyślnie wyłączona. |
| Ruch | binary sensor | Z powiadomień push Reolink, także gdy kamera śpi. |
| Połączenie kamery, Ładowanie | binary sensor | Diagnostyczne. |
| Dioda statusu, Czujnik PIR, Redukcja fałszywych alarmów, Nagrywanie, Dźwięk alarmu przy wykryciu, Powiadomienia push | switch | Ustawienia kamery. |
| Podczerwień | select | Widzenie w nocy: auto, włączone lub wyłączone. |
| Nagrywanie po wykryciu | select | Jak długo kamera nagrywa po wykryciu (na przykład 8 / 15 / 30 s). |
| Czułość PIR | number | 1-100, jak w aplikacji Reolink. |
| Uruchom ponownie, Syrena, Odśwież stan, Zrób zdjęcie | button | Jednorazowe polecenia. |

## Kamery bateryjne

Kamery bateryjne większość czasu śpią, a każde wybudzenie kosztuje baterię. Integracja jest
zaprojektowana z myślą o tym:

- **Odczyt nigdy nie budzi kamery.** Czujniki pokazują ostatnie wartości, które otrzymał most;
  encja kamery, miniatury na dashboardach oraz obrazy *Ostatnie zdjęcie* / *Ostatnie zdarzenie* są
  serwowane z pamięci podręcznej mostu. Jeśli w pamięci nie ma jeszcze zdjęcia, obraz nie jest
  wyświetlany, zamiast budzić kamerę.
- **Budzą ją tylko jawne akcje:** otwarcie podglądu na żywo, naciśnięcie przycisku albo zmiana
  przełącznika, wyboru lub liczby. Most ponownie rozłącza kamerę, gdy jest bezczynna.
- **Świeże zdjęcia na żądanie:** naciśnij **Zrób zdjęcie**. Most odświeża też zdjęcie w pamięci
  podręcznej za każdym razem, gdy kamera i tak jest wybudzona (podgląd na żywo, polecenia, ruch).
- **Ruch bez budzenia:** ruch pochodzi z powiadomień push Reolink, więc działa, gdy kamera śpi.
  Powiadomienia push muszą być włączone w kamerze (przełącznik *Powiadomienia push*) i w aplikacji
  Neolink.
- Wybudzenie kamery 4G przez serwery Reolink może trwać 10-20 sekund, więc podgląd na żywo
  i polecenia mogą potrzebować chwili.

Encje pozostają dostępne, gdy kamera śpi; stają się niedostępne tylko wtedy, gdy sam most jest
nieosiągalny.

## Ograniczenia

- Wymaga forka Neolink z API WebSocket; oryginalny Neolink (MQTT) nie jest obsługiwany.
- Podgląd na żywo korzysta ze strumienia pomocniczego (sub stream).
- Nazwa operatora komórkowego jest znana tylko dla kilku operatorów; pozostali są pokazywani jako
  numeryczny kod MCC+MNC.
- Brak odtwarzania nagrań z karty SD.
- Projekt nie jest powiązany z firmą Reolink ani przez nią wspierany. Reolink jest znakiem towarowym
  swojego właściciela; ikona integracji bazuje na znaku Reolink z
  [home-assistant/brands](https://github.com/home-assistant/brands), z literą „N” zamiast „R”.

## Development

```bash
python3.13 -m venv .venv && .venv/bin/pip install -r requirements_test.txt
.venv/bin/ruff format . && .venv/bin/ruff check .
.venv/bin/python -m pytest
```

Testy uruchamiają fałszywy most (prawdziwy serwer WebSocket na localhost), który mówi tym samym
protokołem co fork Neolink. `deploy.sh` kopiuje integrację do katalogu konfiguracji Home Assistant
zamontowanego przez Sambę (`CONFIG=/path/to/config ./deploy.sh`).

## Licencja

MIT, zobacz [LICENSE](LICENSE).
