# Needle presence sensor, stroke-synced (ESP32)

Prototype for method 2 in VISION_AND_SENSING_PLAN §4.2. A small optical or inductive sensor looks at
the point where the needle tip should be at the bottom of each stroke. A Hall sensor (or the motor
controller's sync output) tells the ESP32 when each stroke happens. If the tip is missing for
`MISSES_FOR_ALARM` strokes in a row while the machine runs at speed, it publishes:

| Topic | Payload |
|---|---|
| `factory/<STATION_CODE>/needle/alarm` | `{"type":"suspected_break","ts":"..."}` |
| `devices/<DEVICE_CODE>/heartbeat` | `{"fw":"1.0.0","rssi":-61}` every 60 s |

It is always a **suspected** break. It goes to review; maintenance confirms it when the needle is replaced,
and only then does it count in needle-batch statistics. Validate it against the replacement log for
4 weeks (target precision ≥ 90 %, recall ≥ 80 %) before rollout.

## Parts

- ESP32 DevKit
- Hall sensor A3144 (or similar, open-collector) + small magnet on the hand-wheel / main shaft, **or** the servo controller's sync / needle-position output (check its voltage: must be 3.3 V or level-shifted)
- Needle presence sensor: fibre-optic reflective sensor with amplifier (preferred: small head fits near the needle plate) or an M5/M8 inductive proximity sensor
- Optocoupler or voltage divider if the sensor output is 12–24 V

## Wiring

| ESP32 | To | Note |
|---|---|---|
| GPIO27 (`STROKE_PIN`) | Hall sensor OUT | internal pull-up; active LOW, one pulse per stroke |
| GPIO26 (`PRESENCE_PIN`) | presence sensor OUT (via optocoupler if > 3.3 V) | `PRESENCE_ACTIVE_LEVEL` = level when the tip is seen |
| 3V3 / GND | sensor supply (if 3.3 V) | otherwise the sensor's own supply, common GND |

Mount the Hall magnet so the pulse comes at a fixed shaft angle. Mount the tip sensor on a bracket on the
needle bar side that cannot touch the needle, thread or presser foot.

## Safety

- Power the machine **off** and lock out the plug while fitting brackets near the needle; a running needle injures fingers.
- Fitting is done with a machine technician; nothing may stop the needle guard or presser foot from working.
- Keep all wiring clear of moving parts and the thread path. The ESP32 is powered from its own 5 V supply.

## Calibration

1. Set `CALIBRATION_LOG 1`, flash, open Serial at 115200 baud.
2. Turn the hand wheel slowly: confirm one stroke per revolution and that `tip_seen` is 1 when the needle is fully down.
3. Run the machine at normal speed with a needle. Adjust `TIP_DELAY_US` (stroke edge → needle at the bottom) until `missing` stays 0. Try ±500 µs steps; pick the middle of the window where it stays 0.
4. Remove the needle (machine off!), run again: `missing` must climb every stroke and an alarm must fire.
5. `MAX_STROKE_GAP_US`: strokes slower than this are not counted, so needle changes on the hand wheel do not alarm.
6. Set `CALIBRATION_LOG 0` for production.

## Notes

- The stroke ISR starts an `esp_timer` one-shot. Verify on the bench with your core version that this is stable
  from the ISR; if not, switch to a hardware timer alarm (`timerAlarm` in core 3.x). If the next stroke
  arrives before the timer fires, that stroke is skipped, not doubled.
- Build: Arduino IDE / `arduino-cli`, board "ESP32 Dev Module", library **PubSubClient** (MIT).
