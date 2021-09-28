#include <Channel.h>
#include <Communication.h>

// A PS Controller for the HV Power Supplies
// * PS1 = Glassman, Einzel Lens, Lower Row of BNC's
// 0-10 V on Voltage control, 0-10 V on Current Control
// * PS2 = Farnell HiVolt, Ion Source HV, Upper Row of BNC's
// 0-10 V on Voltage Control, 0-10 V on Current Control

// Set up serial communication
char inputMessage[128];
mist1::Communication com = mist1::Communication("HVPSController");

// Define pins for power supply control voltages
#define TSY_V_OUT 35

// Define pins for power supply read voltages
#define TSY_V_IN 13

void set_tsy_v (float value){
  analogWrite(TSY_V_OUT, (int)(value / 3.3 * 255.));
}

float get_tsy_v (){
  analogRead(TSY_V_IN);
  delay(1);
  return analogRead(TSY_V_IN) / 1023. * 3.3;
}

void setup() {
  Serial.begin(115200);

  // Init V and I output PWM's
  pinMode(TSY_V_OUT, OUTPUT);

  // Set them to 0 V
  analogWrite(TSY_V_OUT, 0);;
  
  com.add_channel(mist1::Channel("HV_GLAS_V", 'v', 1, &set_tsy_v, &get_tsy_v));
 
}

void loop() {
  
  // GUI Communication.

  if (Serial.available()) {
 
    com.respond_to_input_message();

  }  
}

