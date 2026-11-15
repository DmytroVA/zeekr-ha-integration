# Backlog інтеграції Zeekr

Складено 2026-11-15 за результатами звірки інтеграції 1.7.1 із застосунком Zeekr 5.0.8
і живим HA. Кожне завдання самодостатнє: факти із застосунку вже вписані сюди, повторно
декомпілювати APK не треба.

**Як працювати:** одна сесія — одне завдання. Початок сесії: «Виконай завдання Tn з
`docs/BACKLOG.md`». Після виконання познач `[x]` і допиши рядок «Результат».
Шляхи коду — відносно `custom_components/zeekr/`.

Позначки: 🟢 без авто, механічна робота · 🟡 без авто, треба подумати ·
🚗 потрібна перевірка на авто (реальна команда, підтвердження власника за `CLAUDE.md`).

---

## A. Дефекти

### [x] T1 🟡 Не показувати «вимкнено», коли не прийшов v2.0
- Проблема: `api.py`, `async_get_vehicle_status` — помилка запиту v2.0 ковтається
  (`except ZeekrApiError: v2 = {}`), ключ `v2` у даних зникає. Сутності, що читають лише
  `v2.*` (вартовий, defrost, вентиляція, кермо, сидіння, вікна), на цей цикл стають
  `off`/`closed`.
- Зробити: у `coordinator.py` (`_async_update_data` і `async_refresh_vehicle`), якщо новий
  статус без `v2`, а попередній мав — перенести попередній `v2`. Перший збій логувати
  `warning`, відновлення — `info` (за зразком `_failed_vins`).
- Готово: за відсутності `v2` у відповіді стан цих сутностей не змінюється; логи чисті.
- Результат (1.7.2): `VehicleStatusCoordinator._keep_v2` переносить попередній `v2` в обох
  шляхах оновлення; `FieldObserver` бачить лише реальну відповідь. Логіку перевірено
  ізольованим тестом; на живому HA — регресія (стани, логи), сам збій v2.0 не відтворено.

### [ ] T2 🟡 Черга команд на одне авто
- Проблема: `commands.py`, `async_run_command` — кілька команд одночасно (сцена:
  клімат + сидіння + кермо) ідуть на авто паралельно.
- Зробити: `asyncio.Lock` на VIN у `ZeekrRuntimeData`; тримати його від надсилання до
  отримання вердикту. Оновлення статусу (`async_refresh_vehicle`) — поза блокуванням.
- Готово: дві команди підряд виконуються послідовно, друга не падає.

### [ ] T3 🟢 Мертві сенсори
- `exterior_temperature`: поля `exteriorTemp` немає ні у v1, ні у v2 — завжди `unknown`.
  `average_power_consumption`: завжди `0.0`.
- Зробити: у `sensor.py` обом `entity_registry_enabled_default=False` (нові встановлення).
  Оновити README і `ENTITIES.uk.md`.

### [ ] T4 🟢 FieldObserver пише на диск кожні 5 хв
- Проблема: `coordinator.py`, `FieldObserver.observe` — зміна `updateTime`,
  `pupdateTime`, `temperatureUpdateTime` щоразу ставить `dirty`.
- Зробити: `dirty = True` лише коли з'явилося нове поле або новий зразок у `samples`.
  Лічильник `changes` оновлювати в пам'яті (збережеться разом із наступним записом і при
  зупинці HA).

### [ ] T5 🟢 Мінімальна версія HA
- `hacs.json` заявляє `2024.8.0`. `config_flow.py` використовує `_get_reauth_entry`,
  `_abort_if_unique_id_mismatch`, `async_update_reload_and_abort(data_updates=)`.
- Зробити: з'ясувати за документацією HA, у якій версії з'явилися ці методи
  (ймовірно 2024.11), і виставити її в `hacs.json`.

### [ ] T6 🟢 Документація розходиться з реальністю
- `ENTITIES.uk.md` обіцяє `sensor.zeekr_zeekr_001_raw_<ключ>`. Фактично `raw_` є лише в
  `unique_id`; entity_id будується з назви, з колізіями: `..._voltage_2`,
  `..._distance_to_empty_2`.
- README: «every field the cloud exposes» — неправда. Реєстр `fields.py` узято з моделі
  застосунку; хмара віддає ще поля, яких там немає (`temStatus.powerMode`, `winStatus*`,
  `doorPos*`, `disChargeUAct`/`disChargeIAct`, `washerFluidLevelStatus`,
  `runningStatus.trunIndrLe/Ri`, `position.altitude`).
- Зробити: виправити обидва тексти. Колізії назв: дати raw-сенсорам назви з префіксом
  `Raw ` (unique_id не чіпати; наявні entity_id в реєстрі не зміняться).

### [ ] T7 🟡 Переклади назв сутностей і сервісів
- Проблема: у `strings.json`/`en.json`/`uk.json`/`zh-Hans.json` є лише стани 4 сутностей.
  Назви ~60 сутностей зашиті англійською через `name=`/`_attr_name`; сервіси описані
  тільки в `services.yaml`.
- Зробити: кожній типізованій сутності `translation_key` + запис `entity.<platform>.<key>.name`
  у чотирьох файлах; секція `services` у тих самих файлах. `unique_id` не змінювати.
  Raw-сенсори не перекладати.
- Готово: в українському інтерфейсі назви українські; entity_id існуючих сутностей ті самі.

### [ ] T8 🟢 Картка вартового тягне SDK з CDN
- `www/zeekr-sentinel-card.js:136` — `import("https://unpkg.com/@volcengine/rtc@4.69.2/index.esm.min.js")`.
- Зробити: покласти цей файл у `www/`, зареєструвати другий static path в `__init__.py`
  (`async_setup`), імпортувати локально.

### [ ] T9 🟢 Дублікати керування кліматом
- `switch.air_conditioning` і `number.ac_target_temperature` повторюють `climate`.
- Зробити: обом `entity_registry_enabled_default=False`. Не видаляти: `number` зберігає
  температуру між перезапусками (`RestoreNumber`). Перевірити, що `climate` відновлює
  цільову температуру, коли `number` вимкнено; якщо ні — додати `RestoreEntity` у `climate.py`.

---

## B. Оптимізації

### [ ] T10 🟡 Сенсор «авто активне» і розумне опитування
- Факт: `v2.temStatus.powerMode` змінюється `0`↔`1` (37 змін за 2 доби) — ознака, що
  авто не спить. Зараз 2 запити (v1 + v2) кожні 60 с цілодобово; застосунок читає лише v2.
- Зробити: (1) `binary_sensor` з `v2.temStatus.powerMode == "1"`; (2) v1 і v2 запитувати
  через `asyncio.gather`; (3) v1 опитувати раз на 5 хв (з нього потрібна лише напруга 12 В
  та кілька полів), між опитуваннями переносити попередній; (4) якщо `updateTime` не
  змінювався 10 хв — інтервал 5 хв, інакше 60 с.
- Готово: після команди статус оновлюється так само швидко, як зараз.

### [ ] T11 🚗 Шляхи `/api/v1.0/` для команд
- Факт: застосунок 5.0.8 використовує `/ms-remote-control/api/v1.0/remoteControl/control`
  і `.../api/v1.0/remoteControl/queryProcessResult`. Інтеграція — ті самі шляхи без `/api`.
  Шляхи авторизації (`/ms-user-auth/v1.0/auth/login`, `refreshToken`) не чіпати: точних
  відповідників у застосунку не знайдено.
- Крок 1 (без авто): сервісом `zeekr.api_get` викликати
  `/ms-remote-control/api/v1.0/remoteControl/queryProcessResult` з `params: {sessionId: "0"}`
  і той самий шлях без `/api`; порівняти відповіді.
- Крок 2 (🚗): якщо відповіді однакові — перемкнути обидва шляхи в `api.py`, перевірити
  одну безпечну команду (вартовий увімк./вимк.).

### [ ] T12 🟡 Опис пристрою і список авто
- Список VIN фіксується при вході (`api.vehicles`); модель пристрою — «Vehicle».
- Застосунок: `GET /ms-vehicle-account/api/v1.0/vehicle-detail?os=1`,
  `GET /ms-vehicle-core/api/v1.0/vehicle/favorite-vehicles`.
- Крок 1: подивитися відповіді через `zeekr.api_get`. Крок 2: заповнити `DeviceInfo`
  (модель, версія ПЗ) у `entity.py`.

### [ ] T13 🟢 CI і тести
- Додати GitHub Actions: `hassfest` і `hacs/action`.
- Юніт-тести без HA: `signing.py` (еталонні вектори зняти з поточної реалізації),
  `select.window_state`, `entity.v2_path`/`status_value`/`boolean_value`.

---

## C. Нові функції із застосунку (усі 🚗, перед реалізацією — підтвердження власника)

Спільне: `RemoteControlReq = {serviceId, command, setting:{serviceParameters:[{key,value}], operationScheduling}}`,
вердикт — через наявний `async_run_command`. Спершу кожну команду пробувати сервісом
`zeekr.remote_control`, і лише після підтвердження робити сутність.

### [ ] T14 Заряджання: старт/стоп і ліміт
- Інший ендпоінт: `POST /ms-charge-manage/api/v1.0/charge/control`, тіло
  `{serviceId:"RCS", command, setting:{serviceParameters:[{key,value}]}}`, значення — рядки.
  Відповідь містить `sessionId`.
  - старт: `command:"start"`, `rcs.restart="1"`
  - стоп: `command:"stop"`, `rcs.terminate="1"`
  - ліміт: `command:"start"`, `soc="<значення>"`, `rcs.setting="1"`, `altCurrent="1"`
- Читання ліміту: `GET /ms-charge-manage/api/v1.0/charge/getLatestSoc` → `{soc, socTime}`.
- Крок 1 (без команд): `getLatestSoc` через `zeekr.api_get` — з'ясувати формат `soc`
  (відсотки чи ×10). Крок 2: метод `async_charge_control` в `api.py`. Крок 3: сутності
  `switch` «Заряджання», `number` «Ліміт заряду».
- Перевірка: авто на зарядці.

### [ ] T15 Стан заряджання як у застосунку
- Факт: застосунок визначає стан із `chargerState` і `statusOfChargerConnection`
  (`0` + `dcDcConnectStatus="0"` = не підключено), а не з `isCharging`/`isPluggedIn`.
  Чи працюють ці два бінарні сенсори — не підтверджено (зарядних сесій не спостерігали).
- Зробити: увімкнути raw-сенсори `charger_state`, `status_of_charger_connection`,
  `charge_sts`; провести одну AC-сесію; за `field_observations` скласти таблицю кодів і
  зробити enum-сенсор. Відомі коди `chargerState`: 0/1/7 — не заряджається.

### [ ] T16 Підігрів тягової батареї
- `serviceId:"ZAN"`, `command:"start"|"stop"`, без `setting`. Звичайний ендпоінт команд.
- Стан: `electricVehicleStatus.hvBatteryPreHeatingActive` (є у v2).

### [ ] T17 Лючок зарядки
- Стан уже приходить: `v2.electricVehicleStatus.chargeLidDcAcStatus` і
  `chargeLidAcStatus`; `1` = відкрито, `2` = закрито. Крок 1 без авто: `binary_sensor`.
- Команди (два варіанти в застосунку, залежить від покоління): `RDU`/`RDL` + `command:"start"`
  + `target="back-charge-lid"` або `"front-charge-lid"`; чи `RDO`/`RDC` з тими самими `target`.
  Який лючок на 001 «front», а який «back» — з'ясувати на авто.

### [ ] T18 Замок багажника
- README каже, що `RDL` + `target=trunk` авто відхиляє. У застосунку закриття багажника
  йде з командою **`stop`**: `{serviceId:"RDL", command:"stop", target=trunk}` або
  `{serviceId:"RTL", command:"stop", target=trunk}`. Спробувати обидва.

### [ ] T19 Справжній стан «vent» для вікон
- Зараз `select.py` тримає `vent` 12 годин оптимістично й губить після перезапуску HA.
- Гіпотеза: v1-поле `additionalVehicleStatus.climateStatus.winStatusDriver`
  (`2` закрито, `1` відкрито) реагує на провітрювання — воно змінювалося 4 рази, а
  `winPosDriver` лише 2 (`0`↔`8`).
- Перевірка: команда `vent`, за хвилину — діагностика; подивитися `winStatus*` і `winPos*`.

### [ ] T20 Режими RSM і клаксон
- `RSM` + `rsm`: `4` комфорт паркування (стан `basic.parkComfortState`), `8` кемпінг
  (стан `electricVehicleStatus.campingModeActive`); `command` `start`/`stop`.
- `RHL` + `rhl="horn"` — лише клаксон (є `light-flash` і `horn-light-flash`).

### Свідомо не робимо
Плани заряджання й виїзду, розряд V2L, віддалене паркування й «remote move», цифрові ключі.
