#include <Channel.h>
#include <Communication.h>

// Set up serial communication
char inputMessage[128];
mist1::Communication com = mist1::Communication("Solenoid Valve Switchboard");

volatile int com_flag = 0;

// Solenoid Valve Variables (Relays). x8.
const int solenoidValvePins[] = {22, 24, 26, 28, 30, 32, 34, 36}; //
bool solenoidValveValues[] = {HIGH, HIGH, HIGH, HIGH, HIGH, HIGH, HIGH, HIGH}; // Relays are closed when pulled to ground. Default should be open (HIGH).

// Define pins for error state LED, communication LED
#define LED_ERR 12
#define LED_COM 13

void set_solenoid1(float set_value){
  if (set_value == 1.0) {
    solenoidValveValues[0] = LOW;
    digitalWrite(solenoidValvePins[0], LOW);
  } else {
    solenoidValveValues[0] = HIGH;
    digitalWrite(solenoidValvePins[0], HIGH);
  }
}

float get_solenoid1(){
  if (digitalRead(solenoidValvePins[0]) == LOW) {
    return 1.0;
  } else {
    return 0.0;
  }
}

void set_solenoid2(float set_value){
  if (set_value == 1.0) {
    solenoidValveValues[1] = LOW;
    digitalWrite(solenoidValvePins[1], LOW);
  } else {
    solenoidValveValues[1] = HIGH;
    digitalWrite(solenoidValvePins[1], HIGH);
  }
}

float get_solenoid2(){
  if (digitalRead(solenoidValvePins[1]) == LOW) {
    return 1.0;
  } else {
    return 0.0;
  }
}

void set_solenoid3(float set_value){
  if (set_value == 1.0) {
    solenoidValveValues[2] = LOW;
    digitalWrite(solenoidValvePins[2], LOW);
  } else {
    solenoidValveValues[2] = HIGH;
    digitalWrite(solenoidValvePins[2], HIGH);
  }
}

float get_solenoid3(){
  if (digitalRead(solenoidValvePins[2]) == LOW) {
    return 1.0;
  } else {
    return 0.0;
  }
}

void set_solenoid4(float set_value){
  if (set_value == 1.0) {
    solenoidValveValues[3] = LOW;
    digitalWrite(solenoidValvePins[3], LOW);
  } else {
    solenoidValveValues[3] = HIGH;
    digitalWrite(solenoidValvePins[3], HIGH);
  }
}

float get_solenoid4(){
  if (digitalRead(solenoidValvePins[3]) == LOW) {
    return 1.0;
  } else {
    return 0.0;
  }
}

void set_solenoid5(float set_value){
  if (set_value == 1.0) {
    solenoidValveValues[4] = LOW;
    digitalWrite(solenoidValvePins[4], LOW);
  } else {
    solenoidValveValues[4] = HIGH;
    digitalWrite(solenoidValvePins[4], HIGH);
  }
}

float get_solenoid5(){
  if (digitalRead(solenoidValvePins[4]) == LOW) {
    return 1.0;
  } else {
    return 0.0;
  }
}

void set_solenoid6(float set_value){
  if (set_value == 1.0) {
    solenoidValveValues[5] = LOW;
    digitalWrite(solenoidValvePins[5], LOW);
  } else {
    solenoidValveValues[5] = HIGH;
    digitalWrite(solenoidValvePins[5], HIGH);
  }
}

float get_solenoid6(){
  if (digitalRead(solenoidValvePins[5]) == LOW) {
    return 1.0;
  } else {
    return 0.0;
  }
}

void set_solenoid7(float set_value){
  if (set_value == 1.0) {
    solenoidValveValues[6] = LOW;
    digitalWrite(solenoidValvePins[6], LOW);
  } else {
    solenoidValveValues[6] = HIGH;
    digitalWrite(solenoidValvePins[6], HIGH);
  }
}

float get_solenoid7(){
  if (digitalRead(solenoidValvePins[6]) == LOW) {
    return 1.0;
  } else {
    return 0.0;
  }
}

void set_solenoid8(float set_value){
  if (set_value == 1.0) {
    solenoidValveValues[7] = LOW;
    digitalWrite(solenoidValvePins[7], LOW);
  } else {
    solenoidValveValues[7] = HIGH;
    digitalWrite(solenoidValvePins[7], HIGH);
  }
}

float get_solenoid8(){
  if (digitalRead(solenoidValvePins[7]) == LOW){
    return 1.0;
  } else {
    return 0.0;
  }
}

/*
void dummySetFunc(float set_value){
  //Serial.println("Called the dummy function!");
}

float dummyGetFunc(){
  //Serial.println("Called the dummy function!");
}
*/

void setup()   { 
  // Init Com and Error LED's
  pinMode(LED_ERR, OUTPUT);
  pinMode(LED_COM, OUTPUT);
  digitalWrite(LED_COM, LOW);
  digitalWrite(LED_ERR, LOW);
  
  // Initialise the Arduino data pins.

  // Solenoid Valves.
  for (unsigned i = 0; i < sizeof(solenoidValvePins) / sizeof(int); i++) {
    pinMode(solenoidValvePins[i], OUTPUT);
    digitalWrite(solenoidValvePins[i], HIGH);
  }
      
  Serial.begin(115200);

  com.add_channel(mist1::Channel("SOLENOID1", 's', 1, &set_solenoid1, &get_solenoid1));
  com.add_channel(mist1::Channel("SOLENOID2", 's', 2, &set_solenoid2, &get_solenoid2));
  com.add_channel(mist1::Channel("SOLENOID3", 's', 3, &set_solenoid3, &get_solenoid3));
  com.add_channel(mist1::Channel("SOLENOID4", 's', 4, &set_solenoid4, &get_solenoid4));
  com.add_channel(mist1::Channel("SOLENOID5", 's', 5, &set_solenoid5, &get_solenoid5));
  com.add_channel(mist1::Channel("SOLENOID6", 's', 6, &set_solenoid6, &get_solenoid6));
  com.add_channel(mist1::Channel("SOLENOID7", 's', 7, &set_solenoid7, &get_solenoid7));
  com.add_channel(mist1::Channel("SOLENOID8", 's', 8, &set_solenoid8, &get_solenoid8));
 
}

void loop() {  

  // GUI Communication.
  digitalWrite(LED_COM, LOW);

  if (Serial.available()) {
    
    digitalWrite(LED_COM, HIGH);
    
    com.respond_to_input_message();

  }
}

