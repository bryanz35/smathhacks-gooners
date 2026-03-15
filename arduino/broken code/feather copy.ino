/*
 * ESP32-PICO Feather - WiFi Co-Processor (BIDIRECTIONAL)
 *
 * Arduino --> Feather --> Flask  (sensor data: temp, TDS, quality)
 * Flask   --> Feather --> Arduino (motor commands: F/B/L/R/S)
 *
 * Wiring:
 *   Uno Pin 10 (RX) <-- Feather TX  (direct, 3.3V is fine for Uno input)
 *   Uno Pin 11 (TX) --> Level Shifter --> Feather RX  (5V -> 3.3V)
 *   GND <-> GND
 *
 * Flask endpoints:
 *   POST /command   body: {"cmd":"F"}  -> forwarded to Arduino
 *   GET  /sensors   -> returns latest sensor JSON
 *   GET  /status    -> returns WiFi info
 */

#include <WiFi.h>
#include <WebServer.h>
#include <ArduinoJson.h>

// ---- CONFIGURE THESE ----
const char* WIFI_SSID = "NCSSM-IoT";
const char* WIFI_PASS = "pleat31unwaved";
// -------------------------

WebServer server(80);

// ---------- LATEST SENSOR DATA ----------
struct SensorData {
  float tempC           = 0.0;
  float tempF           = 0.0;
  float tds             = 0.0;
  String quality        = "Unknown";
  unsigned long lastUpdate = 0;
  bool hasData          = false;
} latest;

String serialBuffer = "";

// ---------- PARSE SENSOR LINE FROM ARDUINO ----------
// Expects: "Temp: 24.5 C / 76.1 F  |  TDS: 450 ppm  |  Quality: Good"
bool parseSensorLine(String line) {
  if (!line.startsWith("Temp:")) return false;

  int cIdx = line.indexOf(" C");
  if (cIdx == -1) return false;
  latest.tempC = line.substring(6, cIdx).toFloat();

  int fStart = line.indexOf("/ ") + 2;
  int fIdx   = line.indexOf(" F");
  if (fStart < 2 || fIdx == -1) return false;
  latest.tempF = line.substring(fStart, fIdx).toFloat();

  int tdsStart = line.indexOf("TDS: ") + 5;
  int tdsEnd   = line.indexOf(" ppm");
  if (tdsStart < 5 || tdsEnd == -1) return false;
  latest.tds = line.substring(tdsStart, tdsEnd).toFloat();

  int qStart = line.indexOf("Quality: ") + 9;
  if (qStart < 9) return false;
  latest.quality = line.substring(qStart);
  latest.quality.trim();

  latest.lastUpdate = millis();
  latest.hasData    = true;
  return true;
}

// ---------- HTTP ROUTES ----------

// POST /command  body: {"cmd":"F"}
void handleCommand() {
  if (!server.hasArg("plain")) {
    server.send(400, "application/json", "{\"error\":\"No body\"}");
    return;
  }

  StaticJsonDocument<64> doc;
  DeserializationError err = deserializeJson(doc, server.arg("plain"));
  if (err) {
    server.send(400, "application/json", "{\"error\":\"Bad JSON\"}");
    return;
  }

  String cmd = doc["cmd"].as<String>();
  cmd.trim();
  cmd.toUpperCase();

  if (cmd != "F" && cmd != "B" && cmd != "L" && cmd != "R" && cmd != "S") {
    server.send(400, "application/json", "{\"error\":\"Invalid command\"}");
    return;
  }

  // Forward single char to Arduino over Serial2
  Serial2.print(cmd);

  server.send(200, "application/json", "{\"sent\":\"" + cmd + "\"}");
}

// GET /sensors
void handleSensors() {
  StaticJsonDocument<256> doc;

  if (!latest.hasData) {
    doc["error"] = "No data yet";
    String out;
    serializeJson(doc, out);
    server.send(503, "application/json", out);
    return;
  }

  doc["tempC"]   = latest.tempC;
  doc["tempF"]   = latest.tempF;
  doc["tds"]     = latest.tds;
  doc["quality"] = latest.quality;
  doc["age_ms"]  = millis() - latest.lastUpdate;

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
  // USB debug
  Serial.begin(115200);

  // Serial2 talks to Arduino Uno (pins 16=RX, 17=TX on ESP32)
  Serial2.begin(9600);

  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, HIGH); // OFF

  // Connect to WiFi
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);

  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    digitalWrite(LED_BUILTIN, LOW);
    delay(250);
    digitalWrite(LED_BUILTIN, HIGH);
    delay(250);
    Serial.print(".");
  }

  digitalWrite(LED_BUILTIN, LOW); // Solid ON = connected
  Serial.println("\nConnected! IP: " + WiFi.localIP().toString());

  // Register routes
  server.on("/command", HTTP_POST, handleCommand);
  server.on("/sensors", HTTP_GET,  handleSensors);
  server.on("/status",  HTTP_GET,  handleStatus);
  server.begin();

  Serial.println("Web server started.");
}

// ---------- LOOP ----------
void loop() {
  server.handleClient();

  // Read sensor lines coming in from Arduino
  while (Serial2.available()) {
    char c = Serial2.read();
    if (c == '\n') {
      serialBuffer.trim();
      if (serialBuffer.length() > 0) {
        if (parseSensorLine(serialBuffer)) {
          Serial.println("Parsed: " + serialBuffer); // debug
        }
      }
      serialBuffer = "";
    } else {
      serialBuffer += c;
    }
  }
}
