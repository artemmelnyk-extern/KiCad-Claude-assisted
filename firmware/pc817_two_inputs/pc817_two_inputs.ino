/*
  pc817_two_inputs.ino  (now four inputs; the folder name is kept)
  Reads the four isolated 24 V inputs of the shield (Arduino UNO R4 WiFi or UNO Q; any
  UNO-format board) and prints every edge with its time and the duration of the state that
  just ended. No debounce: the point of the bench is to see bounce and short pulses.

    D2 = e-stop 1   D3 = e-stop 2   D4 = lidar 1   D5 = lidar 2

  Wiring: see docs/pc817_bench.pdf. The board has external 10 k pull-ups to IOREF, so the
  pins are plain INPUTs. Current flows (button released / zone clear) -> pin LOW = OK.
*/

const uint8_t N = 4;
const uint8_t PINS[N] = {2, 3, 4, 5};
const char *NAMES[N] = {"ES1", "ES2", "L1", "L2"};

bool lastOk[N];
unsigned long lastEdgeUs[N];

bool isOk(uint8_t i) { return digitalRead(PINS[i]) == LOW; }

void setup() {
  Serial.begin(115200);
  while (!Serial && millis() < 2000) {}
  unsigned long now = micros();
  for (uint8_t i = 0; i < N; i++) {
    pinMode(PINS[i], INPUT);
    lastOk[i] = isOk(i);
    lastEdgeUs[i] = now;
    Serial.print(NAMES[i]);
    Serial.println(lastOk[i] ? " OK (start)" : " STOP (start)");
  }
}

void loop() {
  for (uint8_t i = 0; i < N; i++) {
    bool ok = isOk(i);
    if (ok == lastOk[i]) continue;
    unsigned long now = micros();
    unsigned long heldUs = now - lastEdgeUs[i];   // wraps correctly after ~71 min
    lastEdgeUs[i] = now;
    lastOk[i] = ok;
    Serial.print(NAMES[i]);
    Serial.print(ok ? " OK   after " : " STOP after ");
    Serial.print(heldUs);
    Serial.println(" us");
  }
}
