/*
 * Feather HUZZAH (ESP8266) - WiFi Co-Processor
 * 
 * This sketch runs on the Feather HUZZAH and handles all WiFi operations.
 * It communicates with the Arduino Uno over hardware Serial (TX/RX pins).
 * 
 * Protocol (newline-delimited):
 *   Uno sends:  "GET:<url>"        -> Feather does HTTP GET, returns response
 *   Uno sends:  "POST:<url>:<body>" -> Feather does HTTP POST
 *   Uno sends:  "STATUS"           -> Feather returns WiFi status
 *   Feather responds: "OK:<data>" or "ERR:<message>"
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClient.h>
// ---- CONFIGURE THESE ----
const char* WIFI_SSID = "NCSSM-IoT";
const char* WIFI_PASS = "pleat31unwaved";
// -------------------------

WiFiClient wifiClient;

void setup() {
  // Serial to communicate with Arduino Uno
  // Match baud rate on both sides
  Serial.begin(9600);
  
  // Built-in LED for status
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, HIGH); // OFF (active low on HUZZAH)
  
  // Connect to WiFi
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  
  // Wait for connection (blink LED while connecting)
  while (WiFi.status() != WL_CONNECTED) {
    digitalWrite(LED_BUILTIN, LOW);
    delay(250);
    digitalWrite(LED_BUILTIN, HIGH);
    delay(250);
  }
  
  // Solid LED = connected
  digitalWrite(LED_BUILTIN, LOW);
  
  // Let the Uno know we're ready
  Serial.println("OK:READY:" + WiFi.localIP().toString());
}

void loop() {
  if (Serial.available()) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    
    if (command.startsWith("GET:")) {
      handleGet(command.substring(4));
    }
    else if (command.startsWith("POST:")) {
      handlePost(command.substring(5));
    }
    else if (command == "STATUS") {
      handleStatus();
    }
    else {
      Serial.println("ERR:Unknown command");
    }
  }
}

void handleGet(String url) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("ERR:WiFi not connected");
    return;
  }
  
  HTTPClient http;
  http.begin(wifiClient, url);
  http.setTimeout(10000);
  
  int httpCode = http.GET();
  
  if (httpCode > 0) {
    String payload = http.getString();
    // Truncate if too long for serial buffer
    if (payload.length() > 512) {
      payload = payload.substring(0, 512);
    }
    Serial.println("OK:" + String(httpCode) + ":" + payload);
  } else {
    Serial.println("ERR:HTTP " + String(httpCode));
  }
  
  http.end();
}

void handlePost(String params) {
  // Format: "url:body"
  int sep = params.indexOf(':');
  if (sep == -1) {
    Serial.println("ERR:Bad POST format");
    return;
  }
  
  String url = params.substring(0, sep);
  String body = params.substring(sep + 1);
  
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("ERR:WiFi not connected");
    return;
  }
  
  HTTPClient http;
  http.begin(wifiClient, url);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(10000);
  
  int httpCode = http.POST(body);
  
  if (httpCode > 0) {
    String payload = http.getString();
    if (payload.length() > 512) {
      payload = payload.substring(0, 512);
    }
    Serial.println("OK:" + String(httpCode) + ":" + payload);
  } else {
    Serial.println("ERR:HTTP " + String(httpCode));
  }
  
  http.end();
}

void handleStatus() {
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("OK:CONNECTED:" + WiFi.localIP().toString() + 
                   ":RSSI=" + String(WiFi.RSSI()));
  } else {
    Serial.println("OK:DISCONNECTED");
  }
}
