// Water Quality Monitor with Dual Pumps
// Hardware: Arduino Uno + Adafruit Motor Shield V3
//           Gravity TDS Meter V1.0 on A1
//           DS18B20 temp probe on D2 (with 4.7k pull-up resistor)
//           DC pump on M1, DC pump on M2

#include <OneWire.h>
#include <DallasTemperature.h>
#include <Adafruit_MotorShield.h>

// ---------- PIN DEFINITIONS ----------
#define TDS_PIN        A1   // TDS meter signal wire
#define TEMP_PIN       2    // DS18B20 data wire

// ---------- TDS SETTINGS ----------
#define VREF           5.0  // Arduino reference voltage
#define SCOUNT         30   // Number of samples to average

// ---------- MOTOR SHIELD SETUP ----------
Adafruit_MotorShield AFMS = Adafruit_MotorShield();
Adafruit_DCMotor *pump1 = AFMS.getMotor(1); // M1
Adafruit_DCMotor *pump2 = AFMS.getMotor(2); // M2

// ---------- PUMP SPEED (0-255) ----------
#define PUMP_SPEED     200  // Adjust this if pumps are too fast/slow

// ---------- TEMP SENSOR SETUP ----------
OneWire oneWire(TEMP_PIN);
DallasTemperature tempSensor(&oneWire);

// ---------- TDS VARIABLES ----------
int analogBuffer[SCOUNT];
int analogBufferIndex = 0;
float averageVoltage = 0;
float tdsValue = 0;
float temperature = 25.0;

// ---------- TIMING ----------
unsigned long lastTDSRead = 0;
unsigned long lastPrint = 0;

// ---------- HELPERS ----------
int getMedianNum(int bArray[], int iFilterLen) {
  int bTab[iFilterLen];
  for (int i = 0; i < iFilterLen; i++) bTab[i] = bArray[i];
  for (int j = 0; j < iFilterLen - 1; j++) {
    for (int i = 0; i < iFilterLen - j - 1; i++) {
      if (bTab[i] > bTab[i + 1]) {
        int temp = bTab[i];
        bTab[i] = bTab[i + 1];
        bTab[i + 1] = temp;
      }
    }
  }
  if (iFilterLen % 2 == 0)
    return (bTab[iFilterLen / 2] + bTab[iFilterLen / 2 - 1]) / 2;
  else
    return bTab[iFilterLen / 2];
}

String getQualityLabel(float tds) {
  if (tds < 300)  return "Excellent";
  if (tds < 600)  return "Good";
  if (tds < 900)  return "Fair";
  if (tds < 1200) return "Poor";
  return "Unsafe";
}

void setup() {
  Serial.begin(9600);
  tempSensor.begin();

  // Start motor shield
  AFMS.begin();

  // Set pump speeds
  pump1->setSpeed(PUMP_SPEED);
  pump2->setSpeed(PUMP_SPEED);

  // Start both pumps running forward continuously
  pump1->run(FORWARD);
  pump2->run(FORWARD);

  Serial.println("Water Quality Monitor starting...");
  Serial.println("Both pumps running.");
  Serial.println("-----------------------------------");
}

void loop() {
  unsigned long now = millis();

  // Sample TDS every 40ms
  if (now - lastTDSRead > 40) {
    lastTDSRead = now;
    analogBuffer[analogBufferIndex] = analogRead(TDS_PIN);
    analogBufferIndex = (analogBufferIndex + 1) % SCOUNT;
  }

  // Print readings every 800ms
  if (now - lastPrint > 800) {
    lastPrint = now;

    // Read temperature
    tempSensor.requestTemperatures();
    float tempC = tempSensor.getTempCByIndex(0);
    float tempF = tempC * 9.0 / 5.0 + 32.0;
    if (tempC != -127.0) temperature = tempC;

    // Calculate TDS with temperature compensation
    averageVoltage = getMedianNum(analogBuffer, SCOUNT) * VREF / 1024.0;
    float compensationCoeff = 1.0 + 0.02 * (temperature - 25.0);
    float compensatedVoltage = averageVoltage / compensationCoeff;
    tdsValue = (133.42 * pow(compensatedVoltage, 3)
              - 255.86 * pow(compensatedVoltage, 2)
              + 857.39 * compensatedVoltage) * 0.5;

    // Print to Serial Monitor
    Serial.print("Temp: ");
    Serial.print(tempC, 1);
    Serial.print(" C  /  ");
    Serial.print(tempF, 1);
    Serial.print(" F     |     TDS: ");
    Serial.print(tdsValue, 0);
    Serial.print(" ppm     |     Quality: ");
    Serial.println(getQualityLabel(tdsValue));
  }
}
