// StitchSense stroke-synced needle presence sensor (VISION_AND_SENSING_PLAN §4.3).
//
//   on stroke interrupt: start a one-shot timer for TIP_DELAY_US
//   on timer: read the presence sensor; if running and tip not seen: missing += 1 else missing = 0
//   if missing >= N: publish factory/<station>/needle/alarm {"type":"suspected_break"}; missing = 0
//
// A sensor alarm is only ever a *suspected* break; maintenance confirms it when the needle is replaced.
// Libraries: PubSubClient (MIT). Board: ESP32 Arduino core 2.x or 3.x (uses ESP-IDF esp_timer).

#include <WiFi.h>
#include <PubSubClient.h>
#include <time.h>
#include "esp_timer.h"
#include "config.h"

WiFiClient net;
PubSubClient mqtt(net);
esp_timer_handle_t tipTimer;
portMUX_TYPE mux = portMUX_INITIALIZER_UNLOCKED;

volatile int64_t lastStrokeUs = 0;
volatile bool strokeCounts = false;   // set by the ISR: this stroke came at machine speed
volatile uint32_t missing = 0;
volatile bool alarmPending = false;
volatile uint32_t strokes = 0;
volatile uint32_t lastReadSeen = 0;   // for calibration logging

char alarmTopic[64];
char heartbeatTopic[64];
unsigned long lastAlarmMs = 0;
unsigned long lastHeartbeatMs = 0;
unsigned long lastReconnectMs = 0;
bool everAlarmed = false;

// Stroke edge: debounce, decide whether the machine is running, schedule the tip read.
void IRAM_ATTR onStroke() {
  int64_t now = esp_timer_get_time();
  int64_t gap = now - lastStrokeUs;
  if (gap < MIN_STROKE_GAP_US) return;  // contact bounce / noise
  lastStrokeUs = now;
  strokeCounts = gap <= MAX_STROKE_GAP_US;  // slow turning (hand wheel, needle change) is not counted
  strokes++;
  if (!esp_timer_is_active(tipTimer)) esp_timer_start_once(tipTimer, TIP_DELAY_US);
}

// Runs in the esp_timer task TIP_DELAY_US after the stroke: the needle tip should be at the sensor.
void onTipTime(void*) {
  bool seen = digitalRead(PRESENCE_PIN) == PRESENCE_ACTIVE_LEVEL;
  portENTER_CRITICAL(&mux);
  lastReadSeen = seen;
  if (!strokeCounts) {
    missing = 0;
  } else if (seen) {
    missing = 0;
  } else if (++missing >= MISSES_FOR_ALARM) {
    alarmPending = true;
    missing = 0;
  }
  portEXIT_CRITICAL(&mux);
}

void isoNow(char* out, size_t len) {
  time_t now = time(nullptr);
  if (now < 1700000000) {
    out[0] = '\0';
    return;
  }
  struct tm t;
  gmtime_r(&now, &t);
  strftime(out, len, "%Y-%m-%dT%H:%M:%SZ", &t);
}

bool publishAlarm() {
  char ts[32], body[96];
  isoNow(ts, sizeof(ts));
  if (ts[0]) snprintf(body, sizeof(body), "{\"type\":\"suspected_break\",\"ts\":\"%s\"}", ts);
  else snprintf(body, sizeof(body), "{\"type\":\"suspected_break\"}");
  return mqtt.publish(alarmTopic, body, false);
}

void publishHeartbeat() {
  char body[96];
  snprintf(body, sizeof(body), "{\"fw\":\"%s\",\"rssi\":%d}", FW_VERSION, WiFi.RSSI());
  mqtt.publish(heartbeatTopic, body, false);
  lastHeartbeatMs = millis();
}

void ensureConnected() {
  if (WiFi.status() != WL_CONNECTED) {
    if (millis() - lastReconnectMs < 5000) return;
    lastReconnectMs = millis();
    WiFi.disconnect();
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    return;
  }
  if (mqtt.connected() || millis() - lastReconnectMs < 3000) return;
  lastReconnectMs = millis();
  if (mqtt.connect(DEVICE_CODE, MQTT_USER, MQTT_PASSWORD)) {
    Serial.println("mqtt connected");
    publishHeartbeat();
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(STROKE_PIN, INPUT_PULLUP);
  pinMode(PRESENCE_PIN, INPUT);
  snprintf(alarmTopic, sizeof(alarmTopic), "factory/%s/needle/alarm", STATION_CODE);
  snprintf(heartbeatTopic, sizeof(heartbeatTopic), "devices/%s/heartbeat", DEVICE_CODE);

  esp_timer_create_args_t args = {};
  args.callback = &onTipTime;
  args.name = "needle_tip";
  ESP_ERROR_CHECK(esp_timer_create(&args, &tipTimer));
  attachInterrupt(digitalPinToInterrupt(STROKE_PIN), onStroke, FALLING);

  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  configTime(0, 0, NTP_SERVER);
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setKeepAlive(30);
}

void loop() {
  ensureConnected();
  mqtt.loop();

  bool fire = false;
  portENTER_CRITICAL(&mux);
  if (alarmPending) {
    alarmPending = false;
    fire = true;
  }
  portEXIT_CRITICAL(&mux);

  // Cooldown: one alarm per break, not one every N strokes while the operator keeps sewing.
  if (fire && (!everAlarmed || millis() - lastAlarmMs >= ALARM_COOLDOWN_MS)) {
    Serial.println("suspected needle break");
    if (mqtt.connected() && publishAlarm()) {
      lastAlarmMs = millis();
      everAlarmed = true;
    } else {
      portENTER_CRITICAL(&mux);
      alarmPending = true;  // keep it until it can be sent
      portEXIT_CRITICAL(&mux);
    }
  }

  if (mqtt.connected() && millis() - lastHeartbeatMs >= HEARTBEAT_MS) publishHeartbeat();

#if CALIBRATION_LOG
  static unsigned long lastLog = 0;
  if (millis() - lastLog >= 200) {
    lastLog = millis();
    Serial.printf("strokes=%lu tip_seen=%lu missing=%lu\n", (unsigned long)strokes, (unsigned long)lastReadSeen,
                  (unsigned long)missing);
  }
#endif
  delay(2);
}
