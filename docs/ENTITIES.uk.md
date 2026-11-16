# Каталог сутностей Zeekr у Home Assistant

Інтеграція читає лише документ статусу **v2.0** — той, що й застосунок. Raw-сутності — це поля моделі даних застосунку Zeekr 5.0.8, які є в документі v2.0 (звірено з живим документом 2026-11-16). З 1.9.0 документ v1.0 не запитується. Поля, які були лише у v1.0, прибрано разом із сутностями: бінарний «Заряджання» (`isCharging`), напруга 12 В, температура ззовні, уся гілка `bigdataVehicleStatus`, `mainBatteryStatus`, `winStatus*`, `drvHeatSts`/`*HeatingDetail` та інші — разом ~100 raw-сенсорів. Під час оновлення з 1.8.x їх видаляє міграція. З 1.9.1 **кожне поле v2.0 має сутність** — типізовану, бінарну, керування або raw (звірено зі знімком і `field_observations` за 2 доби; поля, що приходять лише під час AC-зарядки, ще не спостерігались). Нижче — призначення кожного raw-поля.

**Позначки:** ⭐ корисне у щоденному користуванні · 🔧 діагностика (інколи в пригоді) · ❓ код статусу (сенс відомий, але легенда значень не задокументована виробником) · ⛔ порожнє/не стосується цього EV.

**Разом raw-полів:** 104 (⭐51 · 🔧39 · ❓14 · ⛔0). Плюс 29 типізованих сенсорів, бінарні (підключення кабелю, двері, поворотники, gps_spoofed, active…), трекер, `last_cloud_update` і команди.

Бінарний сенсор **«Авто активне»** (`binary_sensor.*_active`, з 1.9.0) — `on`, поки авто не спить
(`temStatus.powerMode = 1`: поїздка, хтось у салоні, виконується віддалена команда). Від нього
й від `updateTime` залежить опитування: поки авто активне або його `updateTime` змінювався протягом
останніх 10 хв — запит кожні 60 с, інакше кожні 5 хв. Після команди чи кнопки «Оновити статус» —
одразу запит і повернення до 60 с.

**V2L (віддача з авто, з 1.9.1):** `v2l_voltage` / `v2l_current` — напруга й струм на виході розрядника
(`disChargeUAct`/`disChargeIAct`), поза сесією `0`. Під час віддачі одночасно `disChargeConnectStatus = 7`,
`statusOfChargerConnection = 7`, `chargerState = 8` (сесія 2026-11-15: 219,8 В, звірено вольтметром).
`dc_charger_voltage` / `dc_charger_current` — напруга й струм DC-станції (`dcChargePileUAct`/`IAct`), діагностика.
Бінарні `turn_signal_left` / `turn_signal_right` — поворотники (`runningStatus.trunIndrLe`/`trunIndrRi`; так у хмарі, з помилкою в назві).

`engine_status` показує код v2.0 як є (`1` — авто вимкнене; інші значення ще не зафіксовано), а не текст v1.0 `engine-off`. `average_power_consumption` — середній розхід; авто періодично скидає його (зазвичай після зарядки) і до наступної поїздки показує `0`.

Raw-сенсори називаються `Raw <поле>` (напр. *Raw Charger State*) і лежать у категорії Diagnostics пристрою. Entity ID будується з назви: `sensor.zeekr_zeekr_001_raw_charger_state`. Ключі в списку нижче (`raw_ps_latitude` тощо) — частина `unique_id`, а не entity_id. На встановленнях до 1.7.7 entity_id лишаються старими: без `raw_` і з `_2` там, де назви збігалися (`…_distance_to_empty_2`, `…_voltage_2`); змінюється лише назва, яку показує інтерфейс. Типізовані сенсори — без `Raw`.

Назви типізованих сутностей і опис сервісів перекладено англійською, українською та
спрощеною китайською; мова — як у Home Assistant. Entity ID завжди будується з англійської
назви, тож від мови інтерфейсу не залежить. Назви, які ви змінили самі, лишаються вашими.
Raw-сенсори мають англійські назви полів і не перекладаються.

Перемикач *Air conditioning* і число *AC target temperature* дублюють `climate`
(увімкнення і цільову температуру), тому з 1.8.2 на нових встановленнях вони
**вимкнені**. Цільову температуру `climate` тепер сам відновлює після перезапуску.
На вже наявних встановленнях обидві сутності лишаються такими, як були.

Raw-сенсори створюються **вимкненими**: більшість полів на конкретному авто порожні або не змінюються. Увімкніть потрібні на сторінці пристрою. Які поля хмара справді заповнює й як часто вони змінюються, видно в `field_observations` у «Download diagnostics» інтеграції.

## ⭐ Найкорисніші (варто тримати на видноті)

- **Широта (сира; трекер уже бере лише достовірні)** — `raw_ps_latitude` *(гілка: Позиція (GPS))*
- **Довгота (сира)** — `raw_ps_longitude` *(гілка: Позиція (GPS))*
- **Чи можна довіряти GPS — 0 = РЕБ/спуфінг. Основа для gps_spoofed** — `raw_ps_pos_can_be_trusted` *(гілка: Позиція (GPS))*
- **Середня витрата** — `raw_ev_aver_power_consumption` *(гілка: Електрика та заряджання)*
- **Струм заряду AC, A** — `raw_ev_charge_i_act` *(гілка: Електрика та заряджання)*
- **Заряд батареї, % (основний)** — `raw_ev_charge_level` *(гілка: Електрика та заряджання)*
- **Напруга заряду AC, V** — `raw_ev_charge_u_act` *(гілка: Електрика та заряджання)*
- **Запас ходу на батареї, км** — `raw_ev_distance_to_empty_on_battery_only` *(гілка: Електрика та заряджання)*
- **Кабель вставлено** — `raw_ev_is_plugged_in` *(гілка: Електрика та заряджання)*
- **Хвилин до повного (2047 = невідомо)** — `raw_ev_time_to_fully_charged` *(гілка: Електрика та заряджання)*
- **Центральний замок** — `raw_sf_central_locking_status` *(гілка: Двері / замки / безпека)*
- **Замок — водій** — `raw_sf_door_lock_status_driver` *(гілка: Двері / замки / безпека)*
- **Замок — зад.лів** — `raw_sf_door_lock_status_driver_rear` *(гілка: Двері / замки / безпека)*
- **Замок — пас.** — `raw_sf_door_lock_status_passenger` *(гілка: Двері / замки / безпека)*
- **Замок — зад.прав** — `raw_sf_door_lock_status_passenger_rear` *(гілка: Двері / замки / безпека)*
- **Двері — водій** — `raw_sf_door_open_status_driver` *(гілка: Двері / замки / безпека)*
- **Двері — зад.лів** — `raw_sf_door_open_status_driver_rear` *(гілка: Двері / замки / безпека)*
- **Двері — пас.** — `raw_sf_door_open_status_passenger` *(гілка: Двері / замки / безпека)*
- **Двері — зад.прав** — `raw_sf_door_open_status_passenger_rear` *(гілка: Двері / замки / безпека)*
- **Електронний ручник** — `raw_sf_electric_park_brake_status` *(гілка: Двері / замки / безпека)*
- **Капот відкрито** — `raw_sf_engine_hood_open_status` *(гілка: Двері / замки / безпека)*
- **Багажник замкнено** — `raw_sf_trunk_lock_status` *(гілка: Двері / замки / безпека)*
- **Багажник відкрито** — `raw_sf_trunk_open_status` *(гілка: Двері / замки / безпека)*
- **Обігрів скла/дзеркал** — `raw_cl_defrost` *(гілка: Клімат)*
- **Підігрів сидіння — водій, рівень** — `raw_cl_drv_heat_lv` *(гілка: Клімат)*
- **Вентиляція сидіння — водій** — `raw_cl_drv_vent_detail` *(гілка: Клімат)*
- **Температура салону** — `raw_cl_interior_temp` *(гілка: Клімат)*
- **— пасажир** — `raw_cl_pass_heat_lv` *(гілка: Клімат)*
- **— пасажир** — `raw_cl_pass_vent_detail` *(гілка: Клімат)*
- **Передклімат активний** — `raw_cl_pre_climate_active` *(гілка: Клімат)*
- **— зад лівий** — `raw_cl_rl_heat_lv` *(гілка: Клімат)*
- **— зад правий** — `raw_cl_rr_heat_lv` *(гілка: Клімат)*
- **Підігрів керма** — `raw_cl_steer_whl_heating_sts` *(гілка: Клімат)*
- **Коли оновлено клімат-дані** — `raw_cl_temperature_update_time` *(гілка: Клімат)*
- **Рівень гальмівної рідини** — `raw_mt_brake_fluid_level_status` *(гілка: Обслуговування / шини)*
- **Днів до ТО** — `raw_mt_days_to_service` *(гілка: Обслуговування / шини)*
- **Км до ТО** — `raw_mt_distance_to_service` *(гілка: Обслуговування / шини)*
- **Загальний пробіг, км** — `raw_mt_odometer` *(гілка: Обслуговування / шини)*
- **Тиск шини — перед лівий** — `raw_mt_tyre_status_driver` *(гілка: Обслуговування / шини)*
- **Тиск — зад лівий** — `raw_mt_tyre_status_driver_rear` *(гілка: Обслуговування / шини)*
- **Тиск — перед правий** — `raw_mt_tyre_status_passenger` *(гілка: Обслуговування / шини)*
- **Тиск — зад правий** — `raw_mt_tyre_status_passenger_rear` *(гілка: Обслуговування / шини)*
- **Темп шини — перед лівий** — `raw_mt_tyre_temp_driver` *(гілка: Обслуговування / шини)*
- **Темп — зад лівий** — `raw_mt_tyre_temp_driver_rear` *(гілка: Обслуговування / шини)*
- **Темп — перед правий** — `raw_mt_tyre_temp_passenger` *(гілка: Обслуговування / шини)*
- **Темп — зад правий** — `raw_mt_tyre_temp_passenger_rear` *(гілка: Обслуговування / шини)*
- **PM2.5 у салоні** — `raw_po_interior_pm25` *(гілка: Повітря салону)*
- **Рівень PM2.5** — `raw_po_interior_pm25_level` *(гілка: Повітря салону)*
- **Запалення/двигун on/off** — `raw_bs_engine_status` *(гілка: Базовий стан)*
- **Швидкість** — `raw_bs_speed` *(гілка: Базовий стан)*

## За категоріями (усі поля)

### Базовий стан  (8)

| | Поле | Призначення |
|---|---|---|
| ❓ | `carMode` | Режим авто (код) |
| ⭐ | `engineStatus` | Запалення/двигун on/off |
| ❓ | `parkComfortState` | Комфорт під час паркування |
| 🔧 | `repairModeActive` | Режим сервісу/ремонту |
| ⭐ | `speed` | Швидкість |
| 🔧 | `strangerModeActive` | Режим «чужий»/valet |
| ❓ | `usageMode` | Режим використання (код) |
| 🔧 | `vstdModeStatus` | Статус вартового (Sentry) |

### Позиція (GPS)  (5)

| | Поле | Призначення |
|---|---|---|
| 🔧 | `carLocatorStatUploadEn` | Дозвіл авто вивантажувати позицію |
| ⭐ | `latitude` | Широта (сира; трекер уже бере лише достовірні) |
| ⭐ | `longitude` | Довгота (сира) |
| 🔧 | `marsCoordinates` | Координати в китайській системі GCJ-02 (зміщення) чи ні |
| ⭐ | `posCanBeTrusted` | Чи можна довіряти GPS — 0 = РЕБ/спуфінг. Основа для gps_spoofed |

### Електрика та заряджання  (22)

| | Поле | Призначення |
|---|---|---|
| ⭐ | `averPowerConsumption` | Середня витрата (скидається, зазвичай після зарядки) |
| 🔧 | `campingModeActive` | Режим кемпінгу |
| ⭐ | `chargeIAct` | Струм заряду AC, A |
| ⭐ | `chargeLevel` | Заряд батареї, % (основний) |
| 🔧 | `chargeLidAcStatus` | Лючок AC |
| 🔧 | `chargeLidDcAcStatus` | Лючок DC |
| ❓ | `chargeSts` | Код статусу заряду |
| ⭐ | `chargeUAct` | Напруга заряду AC, V |
| ❓ | `chargerState` | Код стану зарядного |
| ❓ | `dcChargeSts` | Код DC-заряду |
| ❓ | `dcDcConnectStatus` | Стан DC-DC |
| ❓ | `disChargeConnectStatus` | Стан розряду/віддачі |
| ⭐ | `distanceToEmptyOnBatteryOnly` | Запас ходу на батареї, км |
| ❓ | `hvBatteryHTMStatus` | Терморегуляція HV |
| 🔧 | `hvBatteryOptimizeFlag` | Оптимізація HV-батареї |
| 🔧 | `hvBatteryPreHeatingActive` | Передпідігрів HV |
| ❓ | `hvTempLevel` | Рівень температури HV (код) |
| ⭐ | `isPluggedIn` | Кабель вставлено |
| 🔧 | `stateOfCharge` | SoC (інколи окремий код) |
| ❓ | `statusOfChargerConnection` | Код підключення зарядного |
| ⭐ | `timeToFullyCharged` | Хвилин до повного (2047 = невідомо) |
| 🔧 | `timeToTargetDisCharged` | Хв до цільового розряду |

### Обслуговування / шини  (22)

| | Поле | Призначення |
|---|---|---|
| ⭐ | `brakeFluidLevelStatus` | Рівень гальмівної рідини |
| ❓ | `washerFluidLevelStatus` | Рівень рідини омивача (код) |
| ⭐ | `daysToService` | Днів до ТО |
| ⭐ | `distanceToService` | Км до ТО |
| ❓ | `dkamModel` | Код моделі цифрового ключа |
| ⭐ | `odometer` | Загальний пробіг, км |
| 🔧 | `tyrePreWarningDriver` | Попередження тиску ПЛ |
| 🔧 | `tyrePreWarningDriverRear` | ЗЛ |
| 🔧 | `tyrePreWarningPassenger` | ПП |
| 🔧 | `tyrePreWarningPassengerRear` | ЗП |
| ⭐ | `tyreStatusDriver` | Тиск шини — перед лівий |
| ⭐ | `tyreStatusDriverRear` | Тиск — зад лівий |
| ⭐ | `tyreStatusPassenger` | Тиск — перед правий |
| ⭐ | `tyreStatusPassengerRear` | Тиск — зад правий |
| ⭐ | `tyreTempDriver` | Темп шини — перед лівий |
| ⭐ | `tyreTempDriverRear` | Темп — зад лівий |
| ⭐ | `tyreTempPassenger` | Темп — перед правий |
| ⭐ | `tyreTempPassengerRear` | Темп — зад правий |
| 🔧 | `tyreTempWarningDriver` | Попередження темп ПЛ |
| 🔧 | `tyreTempWarningDriverRear` | ЗЛ |
| 🔧 | `tyreTempWarningPassenger` | ПП |
| 🔧 | `tyreTempWarningPassengerRear` | ЗП |

### Ходова / ДВЗ-залишки  (4)

| | Поле | Призначення |
|---|---|---|
| 🔧 | `avgSpeed` | Сер. швидкість (256 = невалід) |
| 🔧 | `engineCoolantLevelStatus` | Рівень охолодж. рідини (термоменеджмент) |
| 🔧 | `engineEnableRunning` | Двигун дозволено/працює |
| ⭐ | `tripMeter2` | Лічильник пробігу B |

### Клімат  (27)

| | Поле | Призначення |
|---|---|---|
| ❓ | `activeStatus` | Активність клімату (код) |
| 🔧 | `airBlowerActive` | Обдув салону (вентиляція RCC) |
| 🔧 | `climateOverHeatProActive` | Захист від перегріву салону |
| 🔧 | `currentTemperature` | Поточна задана темп |
| 🔧 | `curtainPos` | Шторка даху |
| ⭐ | `defrost` | Обігрів скла/дзеркал |
| ⭐ | `drvHeatLv` | Підігрів сидіння — водій, рівень |
| ⭐ | `drvVentDetail` | Вентиляція сидіння — водій |
| 🔧 | `fragActive` | Ароматизатор активний |
| 🔧 | `fragItems` | Ароматизатор: картриджі |
| 🔧 | `fragNumber` | — номер |
| ⭐ | `interiorTemp` | Температура салону |
| ⭐ | `passHeatLv` | — пасажир |
| ⭐ | `passVentDetail` | — пасажир |
| ⭐ | `preClimateActive` | Передклімат активний |
| ⭐ | `rlHeatLv` | — зад лівий |
| 🔧 | `rlVentDetail` | — зад лівий |
| ⭐ | `rrHeatLv` | — зад правий |
| 🔧 | `rrVentDetail` | — зад правий |
| ⭐ | `steerWhlHeatingSts` | Підігрів керма |
| 🔧 | `storageBoxStatus` | Статус боксів/бардачка (json) |
| 🔧 | `sunCurtainRearPos` | Задня шторка |
| ⭐ | `temperatureUpdateTime` | Коли оновлено клімат-дані |
| 🔧 | `winPosDriver` | Вікно — водій, положення % |
| 🔧 | `winPosDriverRear` | Вікно — зад.лів |
| 🔧 | `winPosPassenger` | Вікно — пас. |
| 🔧 | `winPosPassengerRear` | Вікно — зад.прав |

### Двері / замки / безпека  (13)

| | Поле | Призначення |
|---|---|---|
| ⭐ | `centralLockingStatus` | Центральний замок |
| ⭐ | `doorLockStatusDriver` | Замок — водій |
| ⭐ | `doorLockStatusDriverRear` | Замок — зад.лів |
| ⭐ | `doorLockStatusPassenger` | Замок — пас. |
| ⭐ | `doorLockStatusPassengerRear` | Замок — зад.прав |
| ⭐ | `doorOpenStatusDriver` | Двері — водій |
| ⭐ | `doorOpenStatusDriverRear` | Двері — зад.лів |
| ⭐ | `doorOpenStatusPassenger` | Двері — пас. |
| ⭐ | `doorOpenStatusPassengerRear` | Двері — зад.прав |
| ⭐ | `electricParkBrakeStatus` | Електронний ручник |
| ⭐ | `engineHoodOpenStatus` | Капот відкрито |
| ⭐ | `trunkLockStatus` | Багажник замкнено |
| ⭐ | `trunkOpenStatus` | Багажник відкрито |

### Повітря салону  (2)

| | Поле | Призначення |
|---|---|---|
| ⭐ | `interiorPM25` | PM2.5 у салоні |
| ⭐ | `interiorPM25Level` | Рівень PM2.5 |

### КПП  (1)

| | Поле | Призначення |
|---|---|---|
| 🔧 | `gearAutoStatus` | Статус авто-режиму КПП |
