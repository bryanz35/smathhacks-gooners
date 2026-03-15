// Arduino Uno R3 — motor control via serial from Python
// Commands: F=forward, B=backward, L=left, R=right, S=stop

const int MOTOR_L_FWD = 3;
const int MOTOR_L_BWD = 5;
const int MOTOR_R_FWD = 6;
const int MOTOR_R_BWD = 9;

const int SPEED = 200;  // PWM 0-255

void setup() {
  Serial.begin(9600);
  pinMode(MOTOR_L_FWD, OUTPUT);
  pinMode(MOTOR_L_BWD, OUTPUT);
  pinMode(MOTOR_R_FWD, OUTPUT);
  pinMode(MOTOR_R_BWD, OUTPUT);
  stopMotors();
}

void loop() {
  if (Serial.available() > 0) {
    char cmd = Serial.read();
    switch (cmd) {
      case 'F': forward();  break;
      case 'B': backward(); break;
      case 'L': left();     break;
      case 'R': right();    break;
      case 'S': stopMotors(); break;
    }
  }
}

void forward() {
  analogWrite(MOTOR_L_FWD, SPEED);
  analogWrite(MOTOR_L_BWD, 0);
  analogWrite(MOTOR_R_FWD, SPEED);
  analogWrite(MOTOR_R_BWD, 0);
}

void backward() {
  analogWrite(MOTOR_L_FWD, 0);
  analogWrite(MOTOR_L_BWD, SPEED);
  analogWrite(MOTOR_R_FWD, 0);
  analogWrite(MOTOR_R_BWD, SPEED);
}

void left() {
  analogWrite(MOTOR_L_FWD, 0);
  analogWrite(MOTOR_L_BWD, 0);
  analogWrite(MOTOR_R_FWD, SPEED);
  analogWrite(MOTOR_R_BWD, 0);
}

void right() {
  analogWrite(MOTOR_L_FWD, SPEED);
  analogWrite(MOTOR_L_BWD, 0);
  analogWrite(MOTOR_R_FWD, 0);
  analogWrite(MOTOR_R_BWD, 0);
}

void stopMotors() {
  analogWrite(MOTOR_L_FWD, 0);
  analogWrite(MOTOR_L_BWD, 0);
  analogWrite(MOTOR_R_FWD, 0);
  analogWrite(MOTOR_R_BWD, 0);
}
