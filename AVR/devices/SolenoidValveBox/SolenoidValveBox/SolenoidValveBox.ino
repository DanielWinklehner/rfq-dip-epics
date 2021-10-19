//#include <Channel.h>
//#include <Communication.h>
#include <libcom1.hpp>

// Set up serial communication
//char inputMessage[128];
//mist1::Communication com = mist1::Communication("Solenoid Valve Switchboard");

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


using mist1::com1::Channel;
MakeChannelMap(lookup, 8, ({
    Channel{ 's', 1, &get_solenoid1, &set_solenoid1},
    Channel{ 's', 2, &get_solenoid2, &set_solenoid2},
    Channel{ 's', 3, &get_solenoid3, &set_solenoid3},
    Channel{ 's', 4, &get_solenoid4, &set_solenoid4},
    Channel{ 's', 5, &get_solenoid5, &set_solenoid5},
    Channel{ 's', 6, &get_solenoid6, &set_solenoid6},
    Channel{ 's', 7, &get_solenoid7, &set_solenoid7},
    Channel{ 's', 8, &get_solenoid8, &set_solenoid8},
  })
);

char serial_in_buffer[128]{0};
// Template parameter is buffer size for the output buffer
mist1::com1::IOHandler<128> io_ctx(
    // Read from the serial port
    [](){
      while (Serial.available() == 0)                       //
      { asm volatile("nop"); }                              //
      Serial.readBytesUntil('\n', serial_in_buffer, 127);   //
      return serial_in_buffer;
    },
    // Write to the serial port
    [](char* str){
      Serial.println(str);
    }
);

mist1::com1::SerialDevice<128, 8> device(io_ctx, lookup);

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
  /*
  com.add_channel(mist1::Channel("SOLENOID1", 's', 1, &set_solenoid1, &get_solenoid1));
  com.add_channel(mist1::Channel("SOLENOID2", 's', 2, &set_solenoid2, &get_solenoid2));
  com.add_channel(mist1::Channel("SOLENOID3", 's', 3, &set_solenoid3, &get_solenoid3));
  com.add_channel(mist1::Channel("SOLENOID4", 's', 4, &set_solenoid4, &get_solenoid4));
  com.add_channel(mist1::Channel("SOLENOID5", 's', 5, &set_solenoid5, &get_solenoid5));
  com.add_channel(mist1::Channel("SOLENOID6", 's', 6, &set_solenoid6, &get_solenoid6));
  com.add_channel(mist1::Channel("SOLENOID7", 's', 7, &set_solenoid7, &get_solenoid7));
  com.add_channel(mist1::Channel("SOLENOID8", 's', 8, &set_solenoid8, &get_solenoid8));
  */
}

void loop() {  

  // GUI Communication.
  digitalWrite(LED_COM, LOW);

  if (Serial.available()) {
    
    digitalWrite(LED_COM, HIGH);
    
    //com.respond_to_input_message();
    device.communicate();
  }
}
