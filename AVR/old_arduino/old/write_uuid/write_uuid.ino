#include <EEPROM.h>

char id[] = "41056695-d374-48cc-8519-17d80c428a4e";  // UUID4. One way of obtaining this is to do "import uuid;  uuid.uuid4()" in a python console.

void setup() {
  // put your setup code here, to run once:
  Serial.begin(9600);
  for (int i=0; i < 36; i++) {
    EEPROM.write(i, id[i]);
  }
}

void loop() {
  // put your main code here, to run repeatedly:

}
