/*
  pc817_two_inputs.ino
  Reads two 24 V signals through PC817 optocouplers on D2 and D3 (Arduino UNO R4 WiFi
  or UNO Q; any UNO-format board) and prints every edge with its time and the duration
  of the state that just ended. No debounce: the point of the bench is to see
  bounce and short pulses.

  Wiring: see docs/pc817_bench.pdf. The board has external 10 k pull-ups to IOREF, so the
  pins are plain INPUTs. 24 V present -> optocoupler conducts -> pin LOW.
*/

const uint8_t PINS[2] = {2, 3};
const char *NAMES[2] = {"IN1", "IN2"};

bool lastOn[2];
unsigned long lastEdgeUs[2];

bool isOn(uint8_t i) { return digitalRead(PINS[i]) == LOW; }

void setup() {
  Serial.begin(115200);
  while (!Serial && millis() < 2000) {}
  unsigned long now = micros();
  for (uint8_t i = 0; i < 2; i++) {
    pinMode(PINS[i], INPUT);
    lastOn[i] = isOn(i);
    lastEdgeUs[i] = now;
    Serial.print(NAMES[i]);
    Serial.println(lastOn[i] ? " 24V ON (start)" : " 24V OFF (start)");
  }
}

void loop() {
  for (uint8_t i = 0; i < 2; i++) {
    bool on = isOn(i);
    if (on == lastOn[i]) continue;
    unsigned long now = micros();
    unsigned long heldUs = now - lastEdgeUs[i];   // wraps correctly after ~71 min
    lastEdgeUs[i] = now;
    lastOn[i] = on;
    Serial.print(NAMES[i]);
    Serial.print(on ? " 24V ON  after " : " 24V OFF after ");
    Serial.print(heldUs);
    Serial.println(" us");
  }
}
