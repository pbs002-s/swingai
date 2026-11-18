# Machine running sensor (ESP32 + SCT-013)

Tells the edge box whether a sewing machine's motor is running, from the motor's supply current.
Brand-agnostic: it only clamps around one supply wire.

Publishes to Mosquitto on the edge box:

| Topic | Payload | When |
|---|---|---|
| `factory/<STATION_CODE>/machine/state` | `{"running":true,"current_a":1.84,"ts":"2026-11-17T09:12:03Z"}` | on change and every 30 s |
| `devices/<DEVICE_CODE>/heartbeat` | `{"fw":"1.0.0","rssi":-61}` | every 60 s |

The edge collector only forwards *changes* to the central API.

## Parts

- ESP32 DevKit (any ESP32 with ADC1 pins)
- SCT-013 **voltage-output** clamp (e.g. SCT-013-030: 30 A = 1 V). Current-output models need a burden resistor; use the voltage type.
- 3.5 mm jack socket, 2 × 10 kΩ resistors, 10 µF capacitor (bias network)
- 5 V USB supply (not taken from the machine)

## Wiring

```
3V3 ──[10k]──┬──[10k]── GND          bias point = 1.65 V
             ├── 10 µF ── GND
             └── CT lead A
CT lead B ───── GPIO34 (CT_ADC_PIN)
```

The ADC sees 1.65 V ± the clamp signal. Use an **ADC1** pin (GPIO32–39); ADC2 stops working while Wi-Fi is on.

## Safety

- **Installing the clamp is electrician work.** Power the machine off and lock out the plug before opening any cover.
- Clamp around **one** conductor (live *or* neutral), never the whole cable: the two currents cancel and it reads 0.
- The clamp is non-invasive: never cut or strip insulation to fit it. Keep the ESP32 and its wiring away from mains terminals.

## Calibration

1. Flash with `config.h` set for the station; open Serial Monitor at 115200 baud.
2. Compare with a clamp meter on the same wire while sewing. Set `CT_CALIBRATION = meter_amps / printed_amps`.
3. Note the current with the motor **idle** (servo motors draw a little) and while **sewing**.
4. Set `RUN_OFF_AMPS` a little above idle and `RUN_ON_AMPS` comfortably below sewing current. The gap between them is the hysteresis: readings in between never change the state.
5. `CONFIRM_READINGS` × `SAMPLE_WINDOW_MS` is how long a change must last (default 3 × 200 ms).
6. Admin → Devices → the sensor → "turn the machine on now": the running signal must appear.

## Build

Arduino IDE or `arduino-cli`, board "ESP32 Dev Module", library **PubSubClient** (MIT).
Do not commit a `config.h` with real Wi-Fi or MQTT passwords.
