// Machine running sensor: per-device settings. Copy, edit, flash. Never commit real passwords.
#pragma once

// Identity
#define STATION_CODE "L1-S01"         // must match the station code in StitchSense
#define DEVICE_CODE  "SENS-L1-S01"    // must match the device code in Admin -> Devices
#define FW_VERSION   "1.0.0"

// Network
#define WIFI_SSID     "factory-sensors"
#define WIFI_PASSWORD "change-me"
#define MQTT_HOST     "192.168.10.2"  // the edge box
#define MQTT_PORT     1883
#define MQTT_USER     "sensor"
#define MQTT_PASSWORD "change-me"
#define NTP_SERVER    "192.168.10.2"  // edge box runs chrony; falls back to send without ts

// Current clamp (SCT-013 voltage-output type, e.g. SCT-013-030 = 30 A per 1 V)
#define CT_ADC_PIN        34           // ADC1 pin (ADC2 does not work while Wi-Fi is on)
#define CT_AMPS_PER_VOLT  30.0f        // from the clamp's label
#define CT_CALIBRATION    1.00f        // multiply after comparing with a clamp meter (see README)
#define SAMPLE_WINDOW_MS  200          // 10 cycles at 50 Hz
#define SAMPLE_INTERVAL_US 250         // 4 kHz sampling

// Running threshold with hysteresis (amps). Measure idle and sewing current first (README).
#define RUN_ON_AMPS   0.60f            // above this -> running
#define RUN_OFF_AMPS  0.35f            // below this -> stopped
#define CONFIRM_READINGS 3             // consecutive windows needed to change state (debounce)

// Publishing
#define REPUBLISH_MS  30000            // resend current state at least this often
#define HEARTBEAT_MS  60000
