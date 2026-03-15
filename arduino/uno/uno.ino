/*
 * Arduino Uno R3 — ROV Sensor + Motor Controller
 *
 * Sensors:  Gravity TDS Meter V1.0 on A1
 *           DS18B20 temp probe on D2 (4.7k pull-up resistor to 5V required)
 * Motors:   Adafruit Motor Shield V3
 *             M1 = left thruster
 *             M2 = right thruster
 * Comms:    SoftwareSerial pins 10 (RX) / 11 (TX) to Feather ESP32
 *             pin 11 (TX) MUST go through a 5V→3.3V level shifter before Feather RX
 *             pin 10 (RX) can connect directly to Feather TX (3.3V is fine for Uno input)
 *
 * Required libraries (install via Library Manager):
 *   OneWire, DallasTemperature, Adafruit Motor Shield V3
 */

#include <OneWire.h>
#include <DallasTemperature.h>
#include <Adafruit_MotorShield.h>
#include <SoftwareSerial.h>

// ---------- PINS ----------
#define TDS_PIN   A1
#define TEMP_PIN  2

// ---------- TDS ----------
#define VREF    5.0   // Arduino supply voltage
#define SCOUNT  30    // Median filter sample count

// ---------- SoftwareSerial to Feather ----------
// RX=10 (from Feather TX), TX=11 (to Feather RX via level shifter)
SoftwareSerial feather(10, 11);

// ---------- TEMP SENSOR ----------
OneWire oneWire(TEMP_PIN);
DallasTemperature tempSensor(&oneWire);

// ---------- MOTOR SHIELD ----------
Adafruit_MotorShield AFMS;
Adafruit_DCMotor *leftMotor  = AFMS.getMotor(1);  // M1
Adafruit_DCMotor *rightMotor = AFMS.getMotor(2);  // M2
#define MOTOR_SPEED 200  // 0–255

// ---------- STATE ----------
int analogBuffer[SCOUNT];
int bufIdx        = 0;
float temperature = 25.0;

unsigned long lastTDSSample = 0;
unsigned long lastSend      = 0;

// ---------- HELPERS ----------
int getMedianNum(int arr[], int len) {
  int tmp[len];
  for (int i = 0; i < len; i++) tmp[i] = arr[i];
  for (int j = 0; j < len - 1; j++)
    for (int i = 0; i < len - j - 1; i++)
      if (tmp[i] > tmp[i+1]) { int t = tmp[i]; tmp[i] = tmp[i+1]; tmp[i+1] = t; }
  return (len % 2 == 0) ? (tmp[len/2] + tmp[len/2-1]) / 2 : tmp[len/2];
}

const char* qualityLabel(float tds) {
  if (tds < 300)  return "Excellent";
  if (tds < 600)  return "Good";
  if (tds < 900)  return "Fair";
  if (tds < 1200) return "Poor";
  return "Unsafe";
}

// ---------- MOTOR CONTROL ----------
void stopMotors()    { leftMotor->run(RELEASE);  rightMotor->run(RELEASE);  }
void driveForward()  { leftMotor->run(FORWARD);  rightMotor->run(FORWARD);  }
void driveBackward() { leftMotor->run(BACKWARD); rightMotor->run(BACKWARD); }
void turnLeft()      { leftMotor->run(BACKWARD); rightMotor->run(FORWARD);  }
void turnRight()     { leftMotor->run(FORWARD);  rightMotor->run(BACKWARD); }

// ---------- SETUP ----------
void setup() {
  Serial.begin(115200);   // USB debug
  feather.begin(9600);    // Talk to Feather ESP32

  tempSensor.begin();

  AFMS.begin();
  leftMotor->setSpeed(MOTOR_SPEED);
  rightMotor->setSpeed(MOTOR_SPEED);
  stopMotors();

  Serial.println("GOONER ROV ready.");
}

// ---------- LOOP ----------
void loop() {
  unsigned long now = millis();

  // -- Motor commands from Feather --
  if (feather.available()) {
    char cmd = feather.read();
    switch (cmd) {
      case 'F': driveForward();  Serial.println("FWD");  break;
      case 'B': driveBackward(); Serial.println("BWD");  break;
      case 'L': turnLeft();      Serial.println("LEFT"); break;
      case 'R': turnRight();     Serial.println("RGHT"); break;
      case 'S': stopMotors();    Serial.println("STOP"); break;
    }
  }

  // -- Sample TDS every 40 ms --
  if (now - lastTDSSample > 40) {
    lastTDSSample = now;
    analogBuffer[bufIdx] = analogRead(TDS_PIN);
    bufIdx = (bufIdx + 1) % SCOUNT;
  }

  // -- Send sensor data to Feather every 800 ms --
  if (now - lastSend > 800) {
    lastSend = now;

    tempSensor.requestTemperatures();
    float tc = tempSensor.getTempCByIndex(0);
    float tf = tc * 9.0 / 5.0 + 32.0;
    if (tc != -127.0) temperature = tc;  // keep last good reading on error

    float avgV  = getMedianNum(analogBuffer, SCOUNT) * VREF / 1024.0;
    float compV = avgV / (1.0 + 0.02 * (temperature - 25.0));
    float tds   = (133.42 * pow(compV, 3)
                 - 255.86 * pow(compV, 2)
                 + 857.39 * compV) * 0.5;

    // Compact JSON — Feather parses this with ArduinoJson
    String json = "{\"tc\":" + String(tc, 1)  +
                  ",\"tf\":" + String(tf, 1)  +
                  ",\"tds\":"+ String(tds, 0) +
                  ",\"q\":\"" + qualityLabel(tds) + "\"}";

    Serial.println(json);    // USB debug (Arduino IDE Serial Monitor)
    feather.println(json);   // Send to Feather
  }
}
