// Needle presence sensor (stroke-synced): per-machine settings. Copy, edit, flash.
#pragma once

// Identity
#define STATION_CODE "L1-S01"
#define DEVICE_CODE  "NEEDLE-L1-S01"
#define FW_VERSION   "1.0.0"

// Network
#define WIFI_SSID     "factory-sensors"
#define WIFI_PASSWORD "change-me"
#define MQTT_HOST     "192.168.10.2"
#define MQTT_PORT     1883
#define MQTT_USER     "sensor"
#define MQTT_PASSWORD "change-me"
#define NTP_SERVER    "192.168.10.2"

// Pins
#define STROKE_PIN    27     // Hall sensor (open-collector, active LOW) or motor sync signal
#define PRESENCE_PIN  26     // optical / inductive needle-tip sensor output
#define PRESENCE_ACTIVE_LEVEL LOW  // level that means "needle tip seen" (check your sensor)

// Timing, from calibration (README). Values in microseconds.
#define TIP_DELAY_US        2500   // stroke edge -> needle at bottom of stroke
#define MIN_STROKE_GAP_US   8000   // debounce: ignore edges closer than this (> 125 strokes/s impossible)
#define MAX_STROKE_GAP_US   200000 // slower than 5 strokes/s = hand-wheel / not running: do not count

// Decision
#define MISSES_FOR_ALARM    5      // N consecutive strokes without the tip -> suspected break
#define ALARM_COOLDOWN_MS   10000  // no repeat alarm for this long
#define HEARTBEAT_MS        60000

// Set to 1 to print each reading on Serial while calibrating (do not leave on in production).
#define CALIBRATION_LOG 0
