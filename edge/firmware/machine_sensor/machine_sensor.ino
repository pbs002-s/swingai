// StitchSense machine running sensor (ESP32 + SCT-013 current clamp).
// Publishes factory/<station>/machine/state {"running":bool,"current_a":float,"ts":"..."} on change
// and every REPUBLISH_MS; devices/<device>/heartbeat {"fw","rssi"} every HEARTBEAT_MS.
// Libraries: PubSubClient (MIT). Board: ESP32 Arduino core 2.x or 3.x.

#include <WiFi.h>
#include <PubSubClient.h>
#include <math.h>
#include <time.h>
#include "config.h"

WiFiClient net;
PubSubClient mqtt(net);

char stateTopic[64];
char heartbeatTopic[64];
bool running = false;
bool stateKnown = false;
int pendingCount = 0;
float lastAmps = 0.0f;
unsigned long lastPublishMs = 0;
unsigned long lastHeartbeatMs = 0;
unsigned long lastReconnectMs = 0;

// RMS current over one window. The clamp is biased at mid-supply, so subtract the window mean.
float readAmpsRms() {
  double sum = 0, sumSq = 0;
  uint32_t n = 0;
  unsigned long start = millis();
  while (millis() - start < SAMPLE_WINDOW_MS) {
    double mv = analogReadMilliVolts(CT_ADC_PIN);
    sum += mv;
    sumSq += mv * mv;
    n++;
    delayMicroseconds(SAMPLE_INTERVAL_US);
  }
  if (n == 0) return 0.0f;
  double mean = sum / n;
  double variance = sumSq / n - mean * mean;
  double vrms = sqrt(variance > 0 ? variance : 0) / 1000.0;
  return (float)(vrms * CT_AMPS_PER_VOLT * CT_CALIBRATION);
}

// ISO 8601 UTC, or empty when NTP has not synced yet (the edge box then uses its own clock).
void isoNow(char* out, size_t len) {
  time_t now = time(nullptr);
  if (now < 1700000000) {  // not synced
    out[0] = '\0';
    return;
  }
  struct tm t;
  gmtime_r(&now, &t);
  strftime(out, len, "%Y-%m-%dT%H:%M:%SZ", &t);
}

void publishState() {
  char ts[32], body[128];
  isoNow(ts, sizeof(ts));
  if (ts[0]) {
    snprintf(body, sizeof(body), "{\"running\":%s,\"current_a\":%.2f,\"ts\":\"%s\"}", running ? "true" : "false",
             lastAmps, ts);
  } else {
    snprintf(body, sizeof(body), "{\"running\":%s,\"current_a\":%.2f}", running ? "true" : "false", lastAmps);
  }
  if (mqtt.publish(stateTopic, body, false)) lastPublishMs = millis();
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
  if (mqtt.connected()) return;
  if (millis() - lastReconnectMs < 3000) return;
  lastReconnectMs = millis();
  if (mqtt.connect(DEVICE_CODE, MQTT_USER, MQTT_PASSWORD)) {
    Serial.println("mqtt connected");
    if (stateKnown) publishState();  // the edge box may have restarted
    publishHeartbeat();
  }
}

void setup() {
  Serial.begin(115200);
  analogReadResolution(12);
  analogSetPinAttenuation(CT_ADC_PIN, ADC_11db);  // full 0-3.3 V range
  snprintf(stateTopic, sizeof(stateTopic), "factory/%s/machine/state", STATION_CODE);
  snprintf(heartbeatTopic, sizeof(heartbeatTopic), "devices/%s/heartbeat", DEVICE_CODE);
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

  lastAmps = readAmpsRms();
  // Hysteresis: between OFF and ON thresholds the state does not change.
  bool candidate = running;
  if (lastAmps >= RUN_ON_AMPS) candidate = true;
  else if (lastAmps <= RUN_OFF_AMPS) candidate = false;

  if (!stateKnown || candidate != running) {
    pendingCount++;
    if (pendingCount >= CONFIRM_READINGS) {
      running = candidate;
      stateKnown = true;
      pendingCount = 0;
      Serial.printf("state %s at %.2f A\n", running ? "running" : "stopped", lastAmps);
      if (mqtt.connected()) publishState();
    }
  } else {
    pendingCount = 0;
  }

  if (mqtt.connected()) {
    if (stateKnown && millis() - lastPublishMs >= REPUBLISH_MS) publishState();
    if (millis() - lastHeartbeatMs >= HEARTBEAT_MS) publishHeartbeat();
  }
}
