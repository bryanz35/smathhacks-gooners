// GOONER ROV — Arduino Uno Main Controller
// Sensors: Gravity TDS Meter V1.0 on A1, DS18B20 on D2
// Motors:  Adafruit Motor Shield V3, thrusters on M1 (left) and M2 (right)
// Comms:   SoftwareSerial on pins 10/11 to talk to Feather

#include <OneWire.h>
#include <DallasTemperature.h>
#include <Adafruit_MotorShield.h>
#include <SoftwareSerial.h>

// ---------- PIN DEFINITIONS ----------
#define TDS_PIN     A1
#define TEMP_PIN    2

// ---------- TDS SETTINGS ----------
#define VREF        5.0
#define SCOUNT      30

// ---------- MOTOR SHIELD ----------
Adafruit_MotorShield AFMS = Adafruit_MotorShield();
Adafruit_DCMotor *leftMotor  = AFMS.getMotor(1); // M1
Adafruit_DCMotor *rightMotor = AFMS.getMotor(2); // M2
#define MOTOR_SPEED 200

// ---------- TEMP SENSOR ----------
OneWire oneWire(TEMP_PIN);
DallasTemperature tempSensor(&oneWire);

// ---------- SOFTWARESERIAL TO FEATHER ----------
// Uno Pin 10 (RX) <-- Feather TX
// Uno Pin 11 (TX) --> Level Shifter --> Feather RX
SoftwareSerial featherSerial(10, 11);

// ---------- TDS VARIABLES ----------
int analogBuffer[SCOUNT];
int analogBufferIndex = 0;
float temperature = 25.0;

// ---------- TIMING ----------
unsigned long lastTDSRead = 0;
unsigned long lastPrint   = 0;

// ---------- HELPERS ----------
int getMedianNum(int bArray[], int iFilterLen) {
  int bTab[iFilterLen];
  for (int i = 0; i < iFilterLen; i++) bTab[i] = bArray[i];
  for (int j = 0; j < iFilterLen - 1; j++)
    for (int i = 0; i < iFilterLen - j - 1; i++)
      if (bTab[i] > bTab[i+1]) {
        int t = bTab[i]; bTab[i] = bTab[i+1]; bTab[i+1] = t;
      }
  return (iFilterLen % 2 == 0)
    ? (bTab[iFilterLen/2] + bTab[iFilterLen/2-1]) / 2
    : bTab[iFilterLen/2];
}

String getQualityLabel(float tds) {
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
  Serial.begin(115200);        // USB debug
  featherSerial.begin(9600);   // Talk to Feather

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

  // --- Receive motor commands FROM Feather ---
  if (featherSerial.available()) {
    char cmd = featherSerial.read();
    switch (cmd) {
      case 'F': driveForward();  Serial.println("CMD: Forward");  break;
      case 'B': driveBackward(); Serial.println("CMD: Backward"); break;
      case 'L': turnLeft();      Serial.println("CMD: Left");     break;
      case 'R': turnRight();     Serial.println("CMD: Right");    break;
      case 'S': stopMotors();    Serial.println("CMD: Stop");     break;
    }
  }

  // --- Sample TDS every 40ms ---
  if (now - lastTDSRead > 40) {
    lastTDSRead = now;
    analogBuffer[analogBufferIndex] = analogRead(TDS_PIN);
    analogBufferIndex = (analogBufferIndex + 1) % SCOUNT;
  }

  // --- Send sensor data TO Feather every 800ms ---
  if (now - lastPrint > 800) {
    lastPrint = now;

    tempSensor.requestTemperatures();
    float tempC = tempSensor.getTempCByIndex(0);
    float tempF = tempC * 9.0 / 5.0 + 32.0;
    if (tempC != -127.0) temperature = tempC;

    float avgVoltage = getMedianNum(analogBuffer, SCOUNT) * VREF / 1024.0;
    float compCoeff  = 1.0 + 0.02 * (temperature - 25.0);
    float compV      = avgVoltage / compCoeff;
    float tdsValue   = (133.42 * pow(compV, 3)
                      - 255.86 * pow(compV, 2)
                      + 857.39 * compV) * 0.5;

    String reading = "Temp: " + String(tempC, 1) +
                     " C / " + String(tempF, 1) +
                     " F  |  TDS: " + String(tdsValue, 0) +
                     " ppm  |  Quality: " + getQualityLabel(tdsValue);

    Serial.println(reading);         // USB debug
    featherSerial.println(reading);  // Send to Feather
  }
}
