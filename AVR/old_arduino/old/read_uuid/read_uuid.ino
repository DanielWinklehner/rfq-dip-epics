#include <EEPROM.h>

char id[37];

void setup() {
  Serial.begin(115200);

  for (int i=0; i < 36; i++) {
    id[i] = EEPROM.read(i);
  }
  
}

void loop() {
  Serial.println(id);

  delay(1000);
}

