# Каталог сутностей Zeekr у Home Assistant

Raw-сутності згенеровано з моделі даних застосунку Zeekr 5.0.8: кожне поле цієї моделі має свій сенсор. Хмара віддає ще кілька полів, яких у моделі немає (`temStatus.powerMode`, `winStatus*`, `doorPos*`, `disChargeUAct`/`disChargeIAct`, `washerFluidLevelStatus`, `runningStatus.trunIndrLe`/`trunIndrRi`, `position.altitude`); сенсорів для них немає, але їх видно в `field_observations` діагностики. Нижче — призначення кожного поля моделі.

**Позначки:** ⭐ корисне у щоденному користуванні · 🔧 діагностика (інколи в пригоді) · ❓ код статусу (сенс відомий, але легенда значень не задокументована виробником) · ⛔ порожнє/не стосується цього EV.

**Разом raw-полів:** 202 (⭐61 · 🔧102 · ❓22 · ⛔17). Плюс 27 типізованих сенсорів, бінарні (заряджання, двері, gps_spoofed…), трекер, `last_cloud_update` і команди.

Типізований сенсор `exterior_temperature` створюється **вимкненим**: поле `exteriorTemp` хмара лишає порожнім і у v1, і у v2, тож він завжди «невідомо». `average_power_consumption` — середній розхід; авто періодично скидає його (зазвичай після зарядки) і до наступної поїздки показує `0`.

Raw-сенсори називаються `Raw <поле>` (напр. *Raw Voltage*) і лежать у категорії Diagnostics пристрою. Entity ID будується з назви: `sensor.zeekr_zeekr_001_raw_voltage`. Ключі в списку нижче (`raw_ps_latitude` тощо) — частина `unique_id`, а не entity_id. На встановленнях до 1.7.7 entity_id лишаються старими: без `raw_` і з `_2` там, де назви збігалися (`…_distance_to_empty_2`, `…_voltage_2`); змінюється лише назва, яку показує інтерфейс. Типізовані сенсори — без `Raw`.

Raw-сенсори створюються **вимкненими**: більшість полів на конкретному авто порожні або не змінюються. Увімкніть потрібні на сторінці пристрою. Які поля хмара справді заповнює й як часто вони змінюються, видно в `field_observations` у «Download diagnostics» інтеграції.

## ⭐ Найкорисніші (варто тримати на видноті)

- **Широта (сира; трекер уже бере лише достовірні)** — `raw_ps_latitude` *(гілка: Позиція (GPS))*
- **Довгота (сира)** — `raw_ps_longitude` *(гілка: Позиція (GPS))*
- **Чи можна довіряти GPS — 0 = РЕБ/спуфінг. Основа для gps_spoofed** — `raw_ps_pos_can_be_trusted` *(гілка: Позиція (GPS))*
- **Середня витрата** — `raw_ev_aver_power_consumption` *(гілка: Електрика та заряджання)*
- **Струм заряду AC, A** — `raw_ev_charge_i_act` *(гілка: Електрика та заряджання)*
- **Заряд батареї, % (основний)** — `raw_ev_charge_level` *(гілка: Електрика та заряджання)*
- **Напруга заряду AC, V** — `raw_ev_charge_u_act` *(гілка: Електрика та заряджання)*
- **Струм DC-заряду, A** — `raw_ev_dc_charge_i_act` *(гілка: Електрика та заряджання)*
- **Запас ходу на батареї, км** — `raw_ev_distance_to_empty_on_battery_only` *(гілка: Електрика та заряджання)*
- **Йде заряджання** — `raw_ev_is_charging` *(гілка: Електрика та заряджання)*
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
- **Швидке охолодження** — `raw_cl_rapid_cooling_active` *(гілка: Клімат)*
- **Швидкий нагрів** — `raw_cl_rapid_warming_active` *(гілка: Клімат)*
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
- **Напруга (HV/12V залежно від гілки)** — `raw_mt_voltage` *(гілка: Обслуговування / шини)*
- **PM2.5 у салоні** — `raw_po_interior_pm25` *(гілка: Повітря салону)*
- **Рівень PM2.5** — `raw_po_interior_pm25_level` *(гілка: Повітря салону)*
- **Запалення/двигун on/off** — `raw_bs_engine_status` *(гілка: Базовий стан)*
- **Час з моменту паркування** — `raw_bs_park_time` *(гілка: Базовий стан)*
- **Швидкість** — `raw_bs_speed` *(гілка: Базовий стан)*
- **Температура тягової батареї** — `raw_bd_battery_temperature` *(гілка: Тягова батарея (bigdata))*
- **Запас ходу на батареї, км** — `raw_bd_distance_to_empty_on_battery_only` *(гілка: Тягова батарея (bigdata))*
- **Напруга (HV/12V залежно від гілки)** — `raw_bd_voltage` *(гілка: Тягова батарея (bigdata))*

## За категоріями (усі поля)

### Базовий стан  (19)

| | Поле | Призначення |
|---|---|---|
| 🔧 | `campVstdModeActive` | Вартовий у режимі кемпінгу |
| ❓ | `carMode` | Режим авто (код) |
| 🔧 | `combinedDistanceToEmpty` | Комбінований запас ходу |
| 🔧 | `danceModeActive` | Світлове «шоу» фарами |
| ⛔ | `distanceToEmpty` | Запас ходу (часто порожній на EV — див. EV-гілку) |
| ⭐ | `engineStatus` | Запалення/двигун on/off |
| 🔧 | `healthChargingActive` | Режим збереження батареї |
| ❓ | `journalLogState` | Стан журналу поїздок |
| 🔧 | `moveCarActive` | Функція «відкотити авто» (асист паркування) |
| 🔧 | `moveCarAuthActive` | — авторизація |
| 🔧 | `moveCarPreAuthActive` | — попередня авторизація |
| ❓ | `parkComfortState` | Комфорт під час паркування |
| ⭐ | `parkTime` | Час з моменту паркування |
| 🔧 | `prkgCameraActive` | Камери паркування активні |
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

### Електрика та заряджання  (50)

| | Поле | Призначення |
|---|---|---|
| ⭐ | `averPowerConsumption` | Середня витрата (скидається, зазвичай після зарядки) |
| 🔧 | `averTraPowerConsumption` | Сер. витрата за поїздку |
| 🔧 | `batteryHeatModeActive` | Підігрів батареї |
| ❓ | `bmshChgConnState` | Стан зʼєднання BMS-heater |
| 🔧 | `campingModeActive` | Режим кемпінгу |
| 🔧 | `cgRemind` | Нагадування про зарядку |
| ⭐ | `chargeIAct` | Струм заряду AC, A |
| ⭐ | `chargeLevel` | Заряд батареї, % (основний) |
| 🔧 | `chargeLidAcStatus` | Лючок AC |
| 🔧 | `chargeLidDcAcStatus` | Лючок DC |
| 🔧 | `chargeLidStatus` | Лючок зарядки |
| ❓ | `chargeSts` | Код статусу заряду |
| ⭐ | `chargeUAct` | Напруга заряду AC, V |
| ❓ | `chargerState` | Код стану зарядного |
| ❓ | `chargingPileType` | Тип ЕЗС |
| ⭐ | `dcChargeIAct` | Струм DC-заряду, A |
| ❓ | `dcChargeSts` | Код DC-заряду |
| ❓ | `dcDcConnectStatus` | Стан DC-DC |
| 🔧 | `dcIAct` | Струм DC (альт.) |
| 🔧 | `dcUAct` | Напруга DC |
| ❓ | `disChargeConnectStatus` | Стан розряду/віддачі |
| ⭐ | `distanceToEmptyOnBatteryOnly` | Запас ходу на батареї, км |
| ⛔ | `fuelChargeStatus` | Паливо (не для EV) |
| 🔧 | `healthChargingCounts` | Лічильник «здорових» зарядів |
| 🔧 | `healthChargingDuration` | Тривалість |
| ❓ | `highVoltageBatteryStatus` | Статус HV-батареї |
| ❓ | `hvBatteryHTMStatus` | Терморегуляція HV |
| 🔧 | `hvBatteryOptimizeFlag` | Оптимізація HV-батареї |
| 🔧 | `hvBatteryPreHeatingActive` | Передпідігрів HV |
| 🔧 | `hvSportActive` | Спорт-режим HV |
| 🔧 | `hvSportPrecondStatus` | Спорт-прекондиціонування |
| 🔧 | `hvSportPrecondTime` | — час |
| ❓ | `hvTempLevel` | Рівень температури HV (код) |
| ⭐ | `isCharging` | Йде заряджання |
| ⭐ | `isPluggedIn` | Кабель вставлено |
| ⛔ | `megaWattCharingHint` | Мегаватне заряджання (не для 001) |
| ⛔ | `megaWattCharingStatus` | — |
| 🔧 | `mmiPwrcnsavg100` | Сер. витрата за 100 км |
| 🔧 | `mmiPwrcnsavg50` | Сер. витрата за 50 км (щиток) |
| ❓ | `mmiPwrcnsavgtabsts` | Режим таблиці витрати |
| 🔧 | `powerLowStatus` | Низький заряд |
| 🔧 | `remainingConsumableMileage` | Залишковий ресурс пробігу |
| 🔧 | `stateOfCharge` | SoC (інколи окремий код) |
| ❓ | `statusOfChargerConnection` | Код підключення зарядного |
| ⭐ | `timeToFullyCharged` | Хвилин до повного (2047 = невідомо) |
| 🔧 | `timeToTargetDisCharged` | Хв до цільового розряду |
| 🔧 | `totalConsumptionMileage` | Сумарний пробіг спожитого |
| 🔧 | `v2xEngConsumption` | V2X споживання |
| 🔧 | `v2xEngWaring` | V2X попередження |
| 🔧 | `v2xStatus` | V2L/V2X віддача |

### Тягова батарея (bigdata)  (8)

| | Поле | Призначення |
|---|---|---|
| ⭐ | `batteryTemperature` | Температура тягової батареї |
| ⭐ | `distanceToEmptyOnBatteryOnly` | Запас ходу на батареї, км |
| ❓ | `maintainInterruptCause` | Причина переривання |
| ❓ | `maintainResponseStatus` | Статус відповіді |
| ❓ | `maintainSettingStatus` | Статус налаштування |
| 🔧 | `maintainTotalEstimateTime` | Обслуговування батареї: оцінка часу |
| 🔧 | `meterDisplaySoc` | SoC як показано на щитку |
| ⭐ | `voltage` | Напруга (HV/12V залежно від гілки) |

### АКБ 12В  (5)

| | Поле | Призначення |
|---|---|---|
| ⭐ | `chargeLevel` | Заряд батареї, % (основний) |
| 🔧 | `energyLevel` | 12V АКБ: рівень енергії |
| 🔧 | `powerLevel` | 12V АКБ: рівень потужності |
| 🔧 | `stateOfCharge` | SoC (інколи окремий код) |
| 🔧 | `stateOfHealth` | SoH (здоровʼя) батареї |

### Обслуговування / шини  (29)

| | Поле | Призначення |
|---|---|---|
| ⭐ | `brakeFluidLevelStatus` | Рівень гальмівної рідини |
| ⭐ | `daysToService` | Днів до ТО |
| ⭐ | `distanceToService` | Км до ТО |
| ❓ | `dkamModel` | Код моделі цифрового ключа |
| ⛔ | `engineOilTemperature` | Темп оливи (не для EV) |
| ⭐ | `odometer` | Загальний пробіг, км |
| 🔧 | `privacyMode` | Приватний режим (не писати трек) |
| 🔧 | `stateOfHealth` | SoH (здоровʼя) батареї |
| 🔧 | `submersionAlrmActive` | Тривога затоплення |
| 🔧 | `tracelessModeActive` | Безслідний режим |
| 🔧 | `typePressureUnit` | Одиниці тиску шин |
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
| ⭐ | `voltage` | Напруга (HV/12V залежно від гілки) |
| 🔧 | `vpdActive` | Захист зони навколо авто |

### Ходова / ДВЗ-залишки  (15)

| | Поле | Призначення |
|---|---|---|
| ⛔ | `aveFuelConsumption` | Витрата палива (не для EV) |
| ⛔ | `aveTraAlcoholConsumption` | Витрата (не для EV) |
| ⛔ | `aveTraFuelConsumption` | — |
| 🔧 | `avgSpeed` | Сер. швидкість (256 = невалід) |
| 🔧 | `engineCoolantLevelStatus` | Рівень охолодж. рідини (термоменеджмент) |
| ⛔ | `engineCoolantTemperature` | Темп охолодж. (порожнє) |
| 🔧 | `engineEnableRunning` | Двигун дозволено/працює |
| ⛔ | `engineOilLevelStatus` | Рівень оливи (не для EV) |
| ⛔ | `engineOilPressureWarning` | Тиск оливи (не для EV) |
| ⛔ | `fuelLevel` | Паливо (не для EV) |
| ⛔ | `fuelLevelPct` | Паливо % (не для EV) |
| ⛔ | `fuelLowStatus` | — |
| ⛔ | `fuelLowWarning` | — |
| ⛔ | `rmtEngStartFuncActive` | Дистанц. запуск ДВЗ (не для EV) |
| ⭐ | `tripMeter2` | Лічильник пробігу B |

### Клімат  (47)

| | Поле | Призначення |
|---|---|---|
| ❓ | `activeStatus` | Активність клімату (код) |
| 🔧 | `airBlowerActive` | Обдув салону (вентиляція RCC) |
| 🔧 | `airCleanSts` | Очищення повітря |
| 🔧 | `carFreezerStatus` | Холодильник у авто |
| 🔧 | `carRefrigeratorStatus` | Холодильник |
| 🔧 | `climateOverHeatProActive` | Захист від перегріву салону |
| 🔧 | `crECOStatus` | ECO-режим клімату |
| 🔧 | `crSetTemp` | Задана темп клімату |
| 🔧 | `currentTemperature` | Поточна задана темп |
| 🔧 | `curtainPos` | Шторка даху |
| ⭐ | `defrost` | Обігрів скла/дзеркал |
| ⭐ | `drvHeatLv` | Підігрів сидіння — водій, рівень |
| ⭐ | `drvVentDetail` | Вентиляція сидіння — водій |
| 🔧 | `fragActive` | Ароматизатор активний |
| 🔧 | `fragItems` | Ароматизатор: картриджі |
| 🔧 | `fragNumber` | — номер |
| ❓ | `htSerilizationSts` | Серіалізація підігріву |
| ⭐ | `interiorTemp` | Температура салону |
| 🔧 | `lrdHeatLv` | — 3-й ряд лівий |
| 🔧 | `lrdVentDetail` | — 3-й ряд лів |
| 🔧 | `oxygenConcLv` | Рівень кисню |
| 🔧 | `oxygenConcValue` | Концентрація кисню |
| 🔧 | `oxygenGeneratorStatus` | Кисневий генератор |
| ⭐ | `passHeatLv` | — пасажир |
| ⭐ | `passVentDetail` | — пасажир |
| ⭐ | `preClimateActive` | Передклімат активний |
| ⭐ | `rapidCoolingActive` | Швидке охолодження |
| ⭐ | `rapidWarmingActive` | Швидкий нагрів |
| ⭐ | `rlHeatLv` | — зад лівий |
| 🔧 | `rlVentDetail` | — зад лівий |
| ⭐ | `rrHeatLv` | — зад правий |
| 🔧 | `rrVentDetail` | — зад правий |
| 🔧 | `rrdHeatLv` | — 3-й ряд правий |
| 🔧 | `rrdVentDetail` | — 3-й ряд прав |
| ⭐ | `steerWhlHeatingSts` | Підігрів керма |
| 🔧 | `storageBoxStatus` | Статус боксів/бардачка (json) |
| 🔧 | `sunCurtainRearPos` | Задня шторка |
| 🔧 | `sunroofOpenStatus` | Люк відкрито |
| 🔧 | `sunroofPos` | Положення люка |
| ⭐ | `temperatureUpdateTime` | Коли оновлено клімат-дані |
| 🔧 | `vocConcentration` | Концентрація VOC |
| 🔧 | `vocGeneratorActive` | Іонізатор/VOC активний |
| 🔧 | `vocLevel` | Рівень VOC (летких сполук) |
| 🔧 | `winPosDriver` | Вікно — водій, положення % |
| 🔧 | `winPosDriverRear` | Вікно — зад.лів |
| 🔧 | `winPosPassenger` | Вікно — пас. |
| 🔧 | `winPosPassengerRear` | Вікно — зад.прав |

### Двері / замки / безпека  (21)

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
| 🔧 | `engineHoodLockStatus` | Капот замкнено |
| ⭐ | `engineHoodOpenStatus` | Капот відкрито |
| 🔧 | `petModeStatus` | Режим «тварина» (клімат у салоні) |
| 🔧 | `privateLockStatus` | Приватний замок |
| ⛔ | `tankFlapStatus` | Лючок баку (не для EV) |
| ⭐ | `trunkLockStatus` | Багажник замкнено |
| 🔧 | `trunkLowerOpenMode` | Режим нижніх |
| 🔧 | `trunkLowerOpenStatus` | Нижні двері багажника |
| ⭐ | `trunkOpenStatus` | Багажник відкрито |
| 🔧 | `trunkUpperOpenMode` | Режим верхніх |
| 🔧 | `trunkUpperOpenStatus` | Верхні двері багажника |

### Повітря салону  (2)

| | Поле | Призначення |
|---|---|---|
| ⭐ | `interiorPM25` | PM2.5 у салоні |
| ⭐ | `interiorPM25Level` | Рівень PM2.5 |

### КПП  (1)

| | Поле | Призначення |
|---|---|---|
| 🔧 | `gearAutoStatus` | Статус авто-режиму КПП |
