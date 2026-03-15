/*
 * Adafruit Feather ESP32 V2 — WiFi Bridge (BIDIRECTIONAL)
 *
 *   Arduino Uno --> Feather --> app.py   sensor data (temp, TDS, quality)
 *   app.py      --> Feather --> Arduino  motor commands (F/B/L/R/S)
 *
 * Wiring (use a 3.3V level shifter on the TX line from the Uno!):
 *   Feather GPIO32 (A7)  <-- Arduino pin 1 TX  [level shifter: 5V->3.3V]
 *   Feather GPIO33 (A9)  --> Arduino pin 0 RX  [direct: 3.3V is fine for Uno input]
 *   GND <-> GND
 *   NOTE: GPIO16/17 are PSRAM on Feather ESP32 V2 — do NOT use them
 *
 * app.py endpoints this server provides:
 *   POST http://<feather_ip>/command   body: {"cmd":"F"}
 *   GET  http://<feather_ip>/sensors
 *   GET  http://<feather_ip>/status
 *
 * Required libraries: ArduinoJson (install via Library Manager)
 */

#include <WiFi.h>
#include <WebServer.h>
#include <ArduinoJson.h>

// ---- WiFi credentials ----
const char* WIFI_SSID = "Bryan_phone";
const char* WIFI_PASS = "bryan123";
// --------------------------

// Serial2 to Arduino Uno
// GPIO16/17 are reserved for PSRAM on Feather ESP32 V2 — use 32/33 instead
HardwareSerial ArduinoSerial(2);
#define ARDUINO_RX_PIN 32   // Feather pin labeled A7  <- Arduino pin 1 (TX) via level shifter
#define ARDUINO_TX_PIN 33   // Feather pin labeled A9  -> Arduino pin 0 (RX)

WebServer server(80);

// Latest sensor data received from the Arduino
struct SensorData {
  float tempC      = 0.0;
  float tempF      = 0.0;
  float tds        = 0.0;
  String quality   = "Unknown";
  unsigned long ts = 0;
  bool hasData     = false;
} latest;

String serialBuf = "";

// Parse compact JSON sent by the Arduino:
// {"tc":24.5,"tf":76.1,"tds":450,"q":"Good"}
bool parseSensorJSON(const String& line) {
  StaticJsonDocument<128> doc;
  if (deserializeJson(doc, line)) return false;
  if (!doc.containsKey("tc")) return false;
  latest.tempC   = doc["tc"];
  latest.tempF   = doc["tf"];
  latest.tds     = doc["tds"];
  latest.quality = doc["q"].as<String>();
  latest.ts      = millis();
  latest.hasData = true;
  return true;
}

// ---------- HTTP HANDLERS ----------

// POST /command   body: {"cmd":"F"}
void handleCommand() {
  if (!server.hasArg("plain")) {
    server.send(400, "application/json", "{\"error\":\"No body\"}");
    return;
  }
  StaticJsonDocument<64> doc;
  if (deserializeJson(doc, server.arg("plain"))) {
    server.send(400, "application/json", "{\"error\":\"Bad JSON\"}");
    return;
  }
  String cmd = doc["cmd"].as<String>();
  cmd.trim();
  cmd.toUpperCase();
  if (cmd != "F" && cmd != "B" && cmd != "L" && cmd != "R" && cmd != "S") {
    server.send(400, "application/json", "{\"error\":\"Invalid cmd\"}");
    return;
  }
  // Forward single char to Arduino over Serial2 (NOT Serial — that goes to USB)
  ArduinoSerial.print(cmd);
  server.send(200, "application/json", "{\"sent\":\"" + cmd + "\"}");
}

// GET /sensors
void handleSensors() {
  if (!latest.hasData) {
    server.send(503, "application/json", "{\"error\":\"No data yet\"}");
    return;
  }
  StaticJsonDocument<128> doc;
  doc["tempC"]   = latest.tempC;
  doc["tempF"]   = latest.tempF;
  doc["tds"]     = latest.tds;
  doc["quality"] = latest.quality;
  doc["age_ms"]  = millis() - latest.ts;
  String out;
  serializeJson(doc, out);
  server.send(200, "application/json", out);
}

// GET /status
void handleStatus() {
  StaticJsonDocument<128> doc;
  doc["connected"] = (WiFi.status() == WL_CONNECTED);
  doc["ip"]        = WiFi.localIP().toString();
  doc["rssi"]      = WiFi.RSSI();
  String out;
  serializeJson(doc, out);
  server.send(200, "application/json", out);
}

// ---------- SETUP ----------
void setup() {
  Serial.begin(115200);  // USB debug only — do NOT use this for Arduino comms
  ArduinoSerial.begin(9600, SERIAL_8N1, ARDUINO_RX_PIN, ARDUINO_TX_PIN);

  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, HIGH);  // OFF

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN));  // blink while connecting
    delay(250);
    Serial.print(".");
  }
  digitalWrite(LED_BUILTIN, LOW);  // solid ON = connected
  Serial.println("\nConnected! IP: " + WiFi.localIP().toString());
  // *** Open Serial Monitor, note this IP, and put it in app.py as FEATHER_IP ***

  server.on("/command", HTTP_POST, handleCommand);
  server.on("/sensors", HTTP_GET,  handleSensors);
  server.on("/status",  HTTP_GET,  handleStatus);
  server.begin();
  Serial.println("HTTP server started.");
}

// ---------- LOOP ----------
void loop() {
  server.handleClient();

  // Read newline-delimited JSON from Arduino
  while (ArduinoSerial.available()) {
    char c = ArduinoSerial.read();
    if (c == '\n') {
      serialBuf.trim();
      if (serialBuf.length() > 0) {
        if (parseSensorJSON(serialBuf)) {
          Serial.println("Sensors updated: " + serialBuf);
        } else {
          Serial.println("Parse failed: " + serialBuf);
        }
      }
      serialBuf = "";
    } else if (c != '\r') {
      serialBuf += c;
    }
  }
}
