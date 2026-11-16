# Zeekr (China cloud) — Home Assistant integration

Unofficial Home Assistant integration for **China-market Zeekr vehicles** that use
the `zeekrlife.com` app cloud (phone number + SMS login, `+86`). It supersedes the
`Admingyu/zeekr-homeassistant` integration: same `zeekr` domain and same entity
unique IDs for the original entities, **plus** read access to every field of the
official app's status model, GPS-jamming (REB) detection, a last-cloud-update freshness
sensor, HACS packaging, and an advanced remote-control service.

> Unofficial project, not affiliated with Zeekr/Geely. It uses the same private
> API the official app calls; the API can change at any time. Control commands act
> on a real car — confirm it is safe before sending them.

## Install (HACS / Marketplace)

1. HACS → ⋮ → **Custom repositories** → add this repo, category **Integration**.
2. Install **Zeekr**, then restart Home Assistant.
3. **Settings → Devices & services → Add integration → Zeekr.**
4. Enter the phone number from the Zeekr app (digits only — the integration sends
   `+86` itself), then the SMS code.

### Migrating from `Admingyu/zeekr-homeassistant`

Both use the `zeekr` domain and the same `custom_components/zeekr` folder, and a
Zeekr account allows only **one** active session (logging in here logs the phone
app out, and vice-versa). Before installing:

1. Remove the old integration entry (**Settings → Devices & services → Zeekr → delete**).
2. Replace the old `custom_components/zeekr` with this one (HACS does this on install).
3. Restart and add the integration again.

Because the domain and the original unique IDs are unchanged, your existing
entity history and dashboards keep working; the many new entities simply appear
alongside them. Use a **dedicated Zeekr account with the car shared to it** so the
integration and your phone app don't evict each other.

## How data freshness works (important)

The integration reads only the **v2.0** status document — the one the official app
uses (refreshed within seconds of a change; carries sentry state, seat heating,
lights …). Since 1.9.0 the older v1.0 document is not requested, and fields only
v1.0 had are not exposed: the *Charging* binary sensor (`isCharging`), the 12 V
battery voltage, the exterior temperature and ~100 raw sensors were removed.

**Adaptive polling.** While the car is awake — `binary_sensor.*_active` is on
(`temStatus.powerMode = 1`) or its `updateTime` changed within the last 10 minutes —
the integration polls every 60 seconds. Once the car has been asleep for 10 minutes
it polls every 5 minutes. A remote command or the *Refresh status* button polls at
once and switches back to 60-second polling, so a command's effect shows up as
quickly as before.

The status document carries the car's own **`updateTime`** (last successful upload
to the cloud). The integration polls every 60 seconds (5 minutes while the car sleeps), but it only ever receives the
document the car last uploaded — so values can be stale even though HA is polling
fine. The **`sensor.*_last_cloud_update`** entity shows that true timestamp; trust
it over Home Assistant's own "last changed".

**GPS jamming / electronic warfare (REB).** The car reports `posCanBeTrusted`. When
its GNSS is jammed or spoofed, the coordinates become false (a common symptom is the
location "teleporting" abroad) and the on-board clock can jump — which can make the
cloud reject further uploads, freezing the data. This integration:

- exposes **`binary_sensor.*_gps_spoofed`** (on = position untrusted), and
- makes the **device tracker hold the last trusted position** instead of following
  the spoofed one.

## Entities (per vehicle)

~50 entities per car are enabled out of the box. The ~169 raw passthrough sensors
(every remaining field of the app's status model) are created **disabled** under
the **Diagnostic** category: most of them are empty or never change on a given
car. Enable the ones you need from the device page.

Raw sensors are named `Raw <field>` (for example *Raw Charger State*), so their entity
IDs look like `sensor.<device>_raw_charger_state`. Installations set up before 1.7.7 keep the
entity IDs they already have (without `raw_`, and with `_2` where two sensors shared
a name, e.g. `…_distance_to_empty_2`, `…_voltage_2`); only the displayed name changes.

The raw registry comes from the app's status model, and the cloud sends a few fields
that model does not list, so they have no raw sensor: for example
`temStatus.powerMode`, `winStatus*`, `doorPos*`, `disChargeUAct`/`disChargeIAct`,
`washerFluidLevelStatus`, `runningStatus.trunIndrLe`/`trunIndrRi`,
`position.altitude`. They still appear in the diagnostics below.

To see which fields your car really fills, use **Download diagnostics** on the
integration: `field_observations` lists every field the cloud returned, grouped
into *changing* (with change count and sample values), *constant* and
*always_empty*. The summary is collected continuously and survives restarts.

`central_locking_status` reports `locked` / `unlocked` and
`electric_park_brake_status` reports `engaged` / `released`. These are stable keys
(use them in automations); the UI shows them translated.

Entity names and service descriptions are translated into English, Ukrainian and
Simplified Chinese and follow the Home Assistant language. Entity IDs are always
built from the English name, so they are the same in every language; names you
renamed yourself stay as you set them. Raw sensors keep their English field names.

| Platform | Entities |
|---|---|
| `sensor` | 29 typed (battery, range, interior temp, tyre pressures/temps, odometer, distances/days to service, charge current/voltage, **V2L discharge voltage/current**, DC charger voltage/current, average consumption (the car resets it periodically, usually after charging), PM2.5, speed, engine status (raw v2.0 code), time-to-full, trip meters, …), `last_cloud_update`, **+ ~70 raw diagnostic sensors (disabled by default) for every remaining field of the v2.0 document** — every field the cloud sends has an entity. Nested/JSON fields (`storageBoxStatus`, `fragItems`, …) are shown as compact JSON. |
| `binary_sensor` | plugged-in, 4 doors, trunk, hood, HV-battery optimization, low/high beam, hazard lights, left/right turn signals, park comfort mode, **active** (car awake), **gps_spoofed** |
| `device_tracker` | location (trusted-position holding) |
| `climate` | **cabin climate**: on/off, target temperature (kept across restarts) |
| `switch` | **sentry mode**, **defrost**, **cabin ventilation**, **steering-wheel heating**; *air conditioning* (on/off shortcut for the climate, disabled by default) |
| `select` | **seat heating** and **seat ventilation** level (`off`, `low`, `medium`, `high`) for driver, passenger and both rear seats; **windows** (`closed`, `vent`, `open`) |
| `lock` | **doors** (central lock; also locks the tailgate) |
| `button` | **refresh**, **rapid warming**, **rapid cooling**, **unlock trunk**; **flash lights**, **flash lights & horn** *(not yet verified, disabled by default)* |
| `number` | run time in 5-minute steps; *AC target temperature* (duplicates the climate target, disabled by default) — local settings shared by the climate controls |

Switches and selectors that depend on optional equipment are only created when the car reports the matching status field. Enable the experimental buttons from the device page if you want to try them.

## Commands

Every command (switches, buttons and the `zeekr.remote_control` service) follows
the official app's flow: the command is sent, then its execution result is polled
every 2 seconds by the `sessionId` the cloud returned, for up to 45 seconds. The
car normally answers within 2–7 seconds. Switches show the new state at once; if
the car refuses or does not answer, the old state comes back and the action fails
with the car's own reason. The status document itself is only refreshed by the
car about once a minute, so it is used as the final reconciliation: after a
confirmed command the new state is held until two separate status documents in a
row report it (a single matching one can be followed by an older-looking one that
rolls the field back), or until 180 seconds have passed, after which the car's
report wins.

To trace a command, enable debug logging for `custom_components.zeekr`: it logs
when each command is queued, sent, executed and followed by a status refresh, and
for every entity holding a commanded state the reported value in each update and
why the hold was released.

Commands to one car are queued: the next one is sent only after the car has
answered the previous one (or the 45-second wait ran out), so a scene that
switches on climate, seat and steering-wheel heating at once runs them in turn
instead of sending them in parallel.

The command envelope (`{serviceId, command, setting:{serviceParameters, operationScheduling}}`)
is the one the official app sends. Individual `serviceId` acceptance depends on the
vehicle generation.

| Function | serviceId | Status | Notes |
|---|---|---|---|
| Refresh status | — | **confirmed** | immediate poll |
| Sentry mode | `RSM` | **confirmed** | state: `basic.vstdModeStatus` 1–4 |
| Air conditioning | `ZAF` | **confirmed** | `AC`, `AC.temp`, `AC.duration`; state `preClimateActive` |
| Rapid warming / cooling | `ZAF` | **confirmed** (warming) | `RW` / `RC` + `.duration`: the app's one-press presets; the car reports them as `preClimateActive`; `AC=false` stops them |
| Defrost | `ZAF` | **confirmed** | `DF`, `DF.level`, `DF.duration`; state `defrost` |
| Cabin ventilation | `RCC` | **confirmed** | `rcc.conditioner`, `rcc.ventilation`, duration×6; state `airBlowerActive` |
| Seat heating | `ZAF` | **confirmed** (driver) | `SH.11` driver, `SH.19` passenger, `SH.21`/`SH.29` rear + `.level`, `.duration` |
| Seat ventilation | `ZAF` | **confirmed** (driver) | `SV.11` … same scheme |
| Steering-wheel heat | `ZAF` | **confirmed** | `SW`, `SW.level`, `SW.duration`; state `steerWhlHeatingSts` 1 = on |
| Door unlock / lock | `RDU` / `RDL` | **confirmed** | command `start`, `door=all`; state `centralLockingStatus` |
| Trunk unlock | `RDU` | **confirmed** | command `start`, `target=trunk`; releases the latch only (the tailgate is then opened by its own button and relocks by itself if not opened). A separate tailgate lock (`RDL` + `target=trunk`) is refused by the car; locking the doors locks it. State `trunkLockStatus` |
| Windows | `RWS` | **confirmed** (vent, close) | `start` + `target=window` (fully open), `start` + `target=ventilate` (vent gap), `stop` + `target=window` (close); state `winPos*` |
| Hood | `RLU` / `RDU` | experimental | generation-dependent |
| Flash lights / flash & horn | `RHL` | not verified | `rhl=light-flash` / `rhl=horn-light-flash` (the app's two find-my-car modes) |

"Confirmed" means verified on a Zeekr 001; other models may differ.

The full catalogue of the app's command identifiers — what each one does, which are
implemented, planned, or deliberately left out and why — is in
[docs/COMMANDS.uk.md](docs/COMMANDS.uk.md) (Ukrainian).

For anything not wired to an entity, use the **`zeekr.remote_control`** service:

```yaml
service: zeekr.remote_control
data:
  vin: "YOURVIN"
  service_id: "RCC"
  command: "start"
  parameters:
    - key: "rcc.conditioner"
      value: "50"
    - key: "rcc.ventilation"
      value: "0"
  duration: 90
```

Other services: `zeekr.get_monthly_statistics`, `zeekr.get_app_messages`.

All services take the `vin`, because one account can hold several vehicles; each
vehicle is its own device and a poll failure of one car does not affect the others.

The sentinel live-video card (`/api/zeekr/zeekr-sentinel-card.js`) can only open a
stream for Home Assistant **administrator** users. It loads the Volcengine RTC SDK
(`@volcengine/rtc` 4.69.2, BSD-3-Clause, bundled unchanged in `www/vendor/`) from
Home Assistant itself, not from a CDN.

## Credits

Builds on the auth/signing work of the `Admingyu/zeekr-homeassistant` and
`RexzeLu/zeekr_ha` community integrations. Field and command models were recovered
from the official Android app's status/command data classes.
