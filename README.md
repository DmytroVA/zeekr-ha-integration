# Zeekr (China cloud) — Home Assistant integration

Unofficial Home Assistant integration for **China-market Zeekr vehicles** that use
the `zeekrlife.com` app cloud (phone number + SMS login, `+86`). It supersedes the
`Admingyu/zeekr-homeassistant` integration: same `zeekr` domain and same entity
unique IDs for the original entities, **plus** exhaustive read coverage of every
field the cloud exposes, GPS-jamming (REB) detection, a last-cloud-update freshness
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

The status document carries the car's own **`updateTime`** (last successful upload
to the cloud). The integration polls every 60 s, but it only ever receives the
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

~223 entities per car. Obscure/opaque fields are grouped under the **Diagnostic**
category so the main view stays clean while nothing is hidden.

| Platform | Entities |
|---|---|
| `sensor` | 27 typed (battery, range, interior/exterior temp, tyre pressures/temps, odometer, distances/days to service, 12 V voltage, charge current/voltage, avg consumption, PM2.5, speed, time-to-full, trip meters, …), `last_cloud_update`, **+ ~169 raw diagnostic sensors covering every remaining field in the app's status model** (BasicVo, ElectricVehicleStatusVo, ClimateStatusVo, DrivingSafetyStatusVo, AdditionalMaintenanceStatusVo, RunningStatusVo, PollutionStatusVo, DrivingBehaviourStatusVo, BigdataVehicleStatusVo, PositionVo, mainBatteryStatus). Nested/JSON fields (`storageBoxStatus`, `fragItems`, …) are shown as compact JSON. |
| `binary_sensor` | charging, plugged-in, 4 doors, trunk, hood, HV-battery optimization, **gps_spoofed** |
| `device_tracker` | location (trusted-position holding) |
| `switch` | **sentry mode** (confirmed), air conditioning *(experimental, disabled by default)* |
| `button` | **refresh** (confirmed), + 10 command buttons *(experimental, disabled by default)*: AC start/stop, rapid cool/warm, defrost start/stop, cabin ventilation start/stop, flash & horn, trunk open |
| `number` | AC target temperature, AC duration (local helpers used by the AC controls) |

Enable the experimental entities from the device page if you want to try them.

## Commands

The command envelope (`{serviceId, command, setting:{serviceParameters, operationScheduling}}`)
is **confirmed** — the sentry command uses it live. Individual `serviceId` acceptance
depends on the vehicle generation, so everything except sentry/refresh is marked
experimental until confirmed on your car.

| Function | serviceId | Status | Notes |
|---|---|---|---|
| Refresh status | — | **confirmed** | immediate poll |
| Sentry mode | `RSM` | **confirmed** | works on the live account |
| Air conditioning | `ZAF` | experimental | params `AC`, `AC.temp`, `AC.duration` |
| Rapid cool / warm | `ZAF` | experimental | AC at 15.5 °C / 28.5 °C |
| Defrost | `ZAF` | experimental | `DF`, `DF.level`, `DF.duration` |
| Cabin ventilation | `RCC` | experimental | `rcc.conditioner`, `rcc.ventilation`, duration×6 |
| Seat heating / vent | `ZAF` (`SH.xx`/`SV.xx`) or `RCE` | experimental | two generations exist; order-sensitive (`.level` before the switch) |
| Steering-wheel heat | `RCE`/`ZAF` | experimental | `rce.heat=steering_wheel` |
| Door unlock / lock | `RDU` / `RDL` | experimental | `target` param (`all`, `front-left`, …); unlock needs the vehicle PIN |
| Trunk open / close | `RTU` / `RTL` | experimental | |
| Hood | `RLU` / `RDU` | experimental | generation-dependent |
| Flash & horn | `RHL` | experimental | |

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

## Credits

Builds on the auth/signing work of the `Admingyu/zeekr-homeassistant` and
`RexzeLu/zeekr_ha` community integrations. Field and command models were recovered
from the official Android app's status/command data classes.
