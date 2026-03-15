// GOONER ROV — Unified Sketch
// Sensors: Gravity TDS Meter V1.0 on A1, DS18B20 on D2
// Motors:  Adafruit Motor Shield V3, thrusters on M1 (left) and M2 (right)
// Serial:  115200 baud — receives F/B/L/R/S commands from Flask

#include <OneWire.h>
#include <DallasTemperature.h>
#include <Adafruit_MotorShield.h>

// ---------- PIN DEFINITIONS ----------
#define TDS_PIN   A1
#define TEMP_PIN  2

// ---------- TDS SETTINGS ----------
#define VREF    5.0
#define SCOUNT  30

// ---------- MOTOR SHIELD ----------
Adafruit_MotorShield AFMS = Adafruit_MotorShield();
Adafruit_DCMotor *leftMotor  = AFMS.getMotor(1); // M1
Adafruit_DCMotor *rightMotor = AFMS.getMotor(2); // M2

#define MOTOR_SPEED 200  // 0-255

// ---------- TEMP SENSOR ----------
OneWire oneWire(TEMP_PIN);
DallasTemperature tempSensor(&oneWire);

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
  for (int j = 0; j < iFilterLen - 1; j++) {
    for (int i = 0; i < iFilterLen - j - 1; i++) {
      if (bTab[i] > bTab[i + 1]) {
        int tmp = bTab[i]; bTab[i] = bTab[i + 1]; bTab[i + 1] = tmp;
      }
    }
  }
  return (iFilterLen % 2 == 0)
    ? (bTab[iFilterLen / 2] + bTab[iFilterLen / 2 - 1]) / 2
    : bTab[iFilterLen / 2];
}

String getQualityLabel(float tds) {
  if (tds < 300)  return "Excellent";
  if (tds < 600)  return "Good";
  if (tds < 900)  return "Fair";
  if (tds < 1200) return "Poor";
  return "Unsafe";
}

// ---------- MOTOR CONTROL ----------
void stopMotors() {
  leftMotor->run(RELEASE);
  rightMotor->run(RELEASE);
}

void driveForward() {
  leftMotor->run(FORWARD);
  rightMotor->run(FORWARD);
}

void driveBackward() {
  leftMotor->run(BACKWARD);
  rightMotor->run(BACKWARD);
}

void turnLeft() {
  leftMotor->run(BACKWARD);
  rightMotor->run(FORWARD);
}

void turnRight() {
  leftMotor->run(FORWARD);
  rightMotor->run(BACKWARD);
}

// ---------- SETUP ----------
void setup() {
  Serial.begin(115200);
  tempSensor.begin();

  AFMS.begin();
  leftMotor->setSpeed(MOTOR_SPEED);
  rightMotor->setSpeed(MOTOR_SPEED);
  stopMotors(); // start stopped, wait for commands

  Serial.println("GOONER ROV ready. Awaiting commands (F/B/L/R/S).");
}

// ---------- LOOP ----------
void loop() {
  unsigned long now = millis();

  // --- Handle incoming motor commands ---
  if (Serial.available() > 0) {
    char cmd = Serial.read();
    switch (cmd) {
      case 'F': driveForward();  break;
      case 'B': driveBackward(); break;
      case 'L': turnLeft();      break;
      case 'R': turnRight();     break;
      case 'S': stopMotors();    break;
    }
  }

  // --- Sample TDS every 40ms ---
  if (now - lastTDSRead > 40) {
    lastTDSRead = now;
    analogBuffer[analogBufferIndex] = analogRead(TDS_PIN);
    analogBufferIndex = (analogBufferIndex + 1) % SCOUNT;
  }

  // --- Print sensor readings every 800ms ---
  if (now - lastPrint > 800) {
    lastPrint = now;

    tempSensor.requestTemperatures();
    float tempC = tempSensor.getTempCByIndex(0);
    float tempF = tempC * 9.0 / 5.0 + 32.0;
    if (tempC != -127.0) temperature = tempC;

    float averageVoltage = getMedianNum(analogBuffer, SCOUNT) * VREF / 1024.0;
    float compensationCoeff = 1.0 + 0.02 * (temperature - 25.0);
    float compensatedVoltage = averageVoltage / compensationCoeff;
    float tdsValue = (133.42 * pow(compensatedVoltage, 3)
                    - 255.86 * pow(compensatedVoltage, 2)
                    + 857.39 * compensatedVoltage) * 0.5;

    Serial.print("Temp: "); Serial.print(tempC, 1);
    Serial.print(" C / ");  Serial.print(tempF, 1);
    Serial.print(" F  |  TDS: "); Serial.print(tdsValue, 0);
    Serial.print(" ppm  |  Quality: "); Serial.println(getQualityLabel(tdsValue));
  }
}