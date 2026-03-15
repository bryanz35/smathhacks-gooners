/*
 * Arduino Uno - Main Controller
 * 
 * Uses a Feather HUZZAH (ESP8266) as a WiFi co-processor
 * via SoftwareSerial on pins 10 (RX) and 11 (TX).
 * 
 * Wiring:
 *   Uno Pin 10 (SS RX) <-- Feather TX  (direct, 3.3V is fine)
 *   Uno Pin 11 (SS TX) --> Level Shifter --> Feather RX  (5V->3.3V)
 *   Uno GND            <-> Feather GND
 * 
 * Hardware Serial (pins 0/1) stays free for USB debugging.
 */

#include <SoftwareSerial.h>

// SoftwareSerial: RX=10, TX=11
SoftwareSerial espSerial(10, 11);

// Timeout for waiting on ESP response (ms)
const unsigned long ESP_TIMEOUT = 15000;

void setup() {
  // USB serial for debugging
  Serial.begin(9600);
  
  // Serial to Feather HUZZAH
  espSerial.begin(9600);
  
  Serial.println("Waiting for Feather HUZZAH to connect to WiFi...");
  
  // Wait for the READY message from the Feather
  String response = waitForResponse(30000);
  if (response.startsWith("OK:READY")) {
    Serial.println("Feather connected! " + response);
  } else {
    Serial.println("WARNING: No READY from Feather. Check wiring/power.");
  }
  
  // ---- Example: fetch data from an API ----
  Serial.println("\nFetching example data...");
  String data = httpGet("http://httpbin.org/get");
  Serial.println("Response: " + data);
}

void loop() {
  // Example: poll a sensor and POST data every 30 seconds
  // Uncomment and modify for your use case:
  
  /*
  int sensorValue = analogRead(A0);
  String json = "{\"sensor\":" + String(sensorValue) + "}";
  String result = httpPost("http://your-server.com/api/data", json);
  Serial.println("POST result: " + result);
  delay(30000);
  */
  
  // For now, check WiFi status every 10 seconds
  String status = getWifiStatus();
  Serial.println("WiFi: " + status);
  delay(10000);
}

// ---- Helper Functions ----

String httpGet(String url) {
  espSerial.println("GET:" + url);
  return waitForResponse(ESP_TIMEOUT);
}

String httpPost(String url, String body) {
  espSerial.println("POST:" + url + ":" + body);
  return waitForResponse(ESP_TIMEOUT);
}

String getWifiStatus() {
  espSerial.println("STATUS");
  return waitForResponse(5000);
}

String waitForResponse(unsigned long timeout) {
  unsigned long start = millis();
  String response = "";
  
  while (millis() - start < timeout) {
    if (espSerial.available()) {
      char c = espSerial.read();
      if (c == '\n') {
        response.trim();
        return response;
      }
      response += c;
    }
  }
  
  return "ERR:Timeout";
}
