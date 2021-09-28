#include <EEPROM.h>

char deviceId[37];
bool deviceIdentified = false;
String inputCommand;

/* 
 *  States: What state the device is on; because you can't really do multi-threadding with Arduinos, we need to keep track of what "state" the device is on to decide what we want the Arduino to do."
 *  
 *  
 */
enum State {
  identification,
  sending_output,
  receiving_input,
  resting
};

State currentState = resting;

void setup() {
  Serial.begin(9600);

  for (int i=0; i < 36; i++) {
    deviceId[i] = EEPROM.read(i);
  }
  
}

void loop() {
  inputCommand = Serial.readString();

  //Serial.println(currentState);

  // Determine what state the Ardunio should be in right now.
  
  if (inputCommand == "identify_yourself") {
    currentState = identification;
  }
  else if (inputCommand == "send_output") {
    currentState = sending_output;
  }
  else if (inputCommand == "receive_input") {
    currentState = receiving_input;
  }
  else if (inputCommand == "identified") {
    currentState = resting;
  }
  else if (inputCommand == "rest") {
    currentState = resting;
  }
  


  if (currentState == identification) {
    Serial.print("device_id=");
    Serial.println(deviceId);
  }
  else if (currentState == sending_output) {
    // For now, just send a random number. 
    Serial.println(random(0, 10));
  }
  else if (currentState == receiving_input) {
    
  }



  delay(50);
}

