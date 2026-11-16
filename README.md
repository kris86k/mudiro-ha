# Mudiro – integracja Home Assistant przez BLE

Integracja przenosi wyłącznie obsługę ogrzewacza Mudiro z zachowanego fragmentu ESPHome do Home Assistant. Nie zawiera sterowania grzałkami, termometrami DS18B20, przekaźnikami ani żadnymi innymi funkcjami z innych urządzeń.

## Co jest przeniesione

- Połączenie BLE przez Home Assistant: lokalny adapter Bluetooth lub ESPHome Bluetooth Proxy.
- Usługa `FFF0`, zapis do `FFF1`, notyfikacje z `FFF2`.
- Odpowiedzi statusowe `5A` o długości 39 bajtów.
- Odpowiedzi ustawień `5C 16` (24 bajty) i potwierdzenia `5C 12` (20 bajtów), z walidacją CRC Modbus.
- Dynamiczne zapytanie o ustawienia `5C` ze znacznikiem czasu.
- AUTO/MANUAL, zakres nastawy 8–35, PLUS/MINUS.
- WŁĄCZ/WYŁĄCZ z niezmienionymi ramkami źródłowymi.
- AUTO START-STOP z aktualnego bloku danych 5C i modyfikacją bajtu x[14].
- Wszystkie sensory i pola diagnostyczne z zachowanego fragmentu YAML.
- Automatyczne ponawianie połączenia po rozłączeniu.

## Wymagania Bluetooth

Home Assistant musi mieć działającą integrację Bluetooth. Każde ESPHome, które ma pośredniczyć w połączeniu, musi być urządzeniem ESP32 z komponentem Bluetooth Proxy i obsługą aktywnych połączeń GATT. Przykładowa sekcja w konfiguracji takiego węzła:

```yaml
esp32_ble_tracker:
  scan_parameters:
    active: true

bluetooth_proxy:
  active: true
```

Jeżeli węzeł ma już `esp32_ble_tracker`, zachowaj jego istniejące ustawienia i dodaj tylko brakującą sekcję `bluetooth_proxy`. Nie usuwaj pozostałych komponentów ani automatyzacji. Nie wgrywaj osobnego firmware Mudiro do każdego ESP32: proxy przekazuje obsługę BLE do Home Assistant. Zwykłe ESPHome na ESP8266 albo ESP32 bez aktywnego Bluetooth Proxy nie stanie się bramką BLE.

## Instalacja

1. Zrób kopię zapasową Home Assistant.
2. Upewnij się, że integracja **Bluetooth** jest widoczna w **Ustawienia → Urządzenia i usługi**. Jeśli jej nie ma, dodaj ją.
3. Skopiuj cały katalog `custom_components/mudiro` z repozytorium do katalogu `/config/custom_components/mudiro` w Home Assistant. Po skopiowaniu struktura ma wyglądać tak:

   ```text
   /config/custom_components/mudiro/manifest.json
   /config/custom_components/mudiro/__init__.py
   /config/custom_components/mudiro/config_flow.py
   /config/custom_components/mudiro/coordinator.py
   /config/custom_components/mudiro/protocol.py
   /config/custom_components/mudiro/sensor.py
   /config/custom_components/mudiro/binary_sensor.py
   /config/custom_components/mudiro/switch.py
   /config/custom_components/mudiro/button.py
   /config/custom_components/mudiro/translations/pl.json
   ```
4. Uruchom ponownie Home Assistant.
5. Otwórz **Ustawienia → Urządzenia i usługi → Dodaj integrację**.
6. Wyszukaj **Mudiro ogrzewacz BLE**.
7. Wprowadź adres MAC swojego ogrzewacza (nie jest zapisany w repozytorium), a interwał pozostaw początkowo na `3` sekundy.
8. Zapisz integrację. Po połączeniu pojawią się sensory, dwa przełączniki i pięć przycisków.

## Ważne przed pierwszym połączeniem

- Jeżeli jakikolwiek dotychczasowy ESPHome nadal utrzymuje aktywny `ble_client` do ogrzewacza, wyłącz tylko to połączenie/klienta BLE przed uruchomieniem integracji HA. Nie usuwaj pozostałych części konfiguracji ESPHome. Piec powinien mieć jednego klienta GATT sterującego nim w danym momencie.
- W Home Assistant sprawdź **Ustawienia → Urządzenia i usługi → Bluetooth → Adapters**. Co najmniej jeden adapter/proxy musi widzieć piec i obsługiwać aktywne połączenia GATT. Dla adapterów ustawionych na `Auto` HA może uruchomić skanowanie aktywne na żądanie; nie ustawiaj proxy używanego do Mudiro wyłącznie w trybie `Passive`.
- HA wybiera dostępny adapter BLE, który widzi piec. Po zerwaniu sesji integracja ponawia połączenie i HA może wybrać inny dostępny proxy. Nie jest to jednak przełączenie bez przerwy w trakcie aktywnej sesji.
- `AUTO START-STOP` będzie dostępny dopiero po odebraniu i sprawdzeniu CRC ramki 5C. W trybie MANUAL polecenie jest blokowane zgodnie z oryginalnym kodem.

## Encje

### Stan i pomiary

- Mudiro połączenie BLE
- Mudiro napięcie
- Mudiro wartość nastawy x15
- Mudiro temperatura zadana AUTO
- Mudiro poziom grzania
- Mudiro temperatura pieca
- Mudiro temperatura pomieszczenia
- Mudiro poziom paliwa
- Mudiro obroty wentylatora
- Mudiro stan
- Mudiro tryb regulacji
- Mudiro błąd

### Sterowanie

- Mudiro tryb AUTO
- Mudiro AUTO START-STOP
- Mudiro WŁĄCZ
- Mudiro WYŁĄCZ
- Mudiro PLUS
- Mudiro MINUS
- Mudiro odśwież status

### Diagnostyka

- Mudiro AUTO START-STOP x14
- Mudiro pole x11 TEST
- Mudiro pompka x11 TEST
- Mudiro pola x5, x9, x10, x12, x13, x14, x16, x18, x20 TEST
- Mudiro wysokość NPM TEST
- Mudiro licznik ramki x36 TEST
- Mudiro kody stanu, błędu i trybu
- Mudiro ostatnia ramka BLE
- Mudiro surowa ramka 5A
- Mudiro surowa ramka 5C
- Mudiro zmiany pól TEST

## Uwagi o wierności protokołu

Kod poleceń i offsety są przeniesione z dostarczonego `mudiro_full_fragment.yaml`. Zachowany fragment nie weryfikował CRC głównej ramki 5A, więc integracja również nie dopisuje niepotwierdzonej walidacji. CRC ramek 5C jest walidowane zgodnie z kolejnością bajtów w źródle.

Paczka została sprawdzona składniowo i testami funkcji protokołu, ale nie mogła zostać przetestowana z fizycznym ogrzewaczem ani z Twoją instalacją Home Assistant. Pierwsze uruchomienie należy potraktować jako test komunikacji: sprawdzić połączenie BLE, odebranie ramki 5A/5C i dopiero potem używać przycisków WŁĄCZ/WYŁĄCZ.
