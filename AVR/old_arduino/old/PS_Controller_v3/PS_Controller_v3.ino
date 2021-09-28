#include "Communication.h"

// Define pins for error state LED, communication LED
#define LED_ERR 39
#define LED_COM 33
#define LED_OPEN 35
#define LED_CLOSED 37

// Define pins for power supply control voltages
#define PS1_V_OUT 12  // Cave: For Timer1, "2" maps to pin 12
#define PS1_I_OUT 11  // Cave: For Timer1, "1" maps to pin 11
#define PS2_V_OUT 10
#define PS2_I_OUT 9

// Define pins for power supply read voltages
#define PS1_V_IN 0
#define PS1_I_IN 2
#define PS2_V_IN 3
#define PS2_I_IN 1

// Define pins for relays (interlock, PS on/off)
#define RELAY1 14
#define RELAY2 15
#define RELAY3 16
#define RELAY4 17

// Set up serial communication
char inputMessage[128];
mist1::Communication com = mist1::Communication();

/*
// function object prototype for setting relay state
typedef struct setRelay {
 // constructor
 setRelay (const uint8_t relay) : relay_ (relay) {}
 // operator ()
 void operator () (int state)
   {
     if (state == 1) {
       digitalWrite(relay_, LOW);
     } else if (state == 0) {
       digitalWrite(relay_, HIGH);
     }
   }  // end of operator ()

 private:    
   uint8_t relay_;
};

setRelay set_relay1 (RELAY1);
setRelay set_relay2 (RELAY2);
setRelay set_relay3 (RELAY3);
setRelay set_relay4 (RELAY4);
*/

void set_relay1 (int state){
  if (state == 1) {
    digitalWrite(RELAY1, LOW);
  } else if (state == 0) {
    digitalWrite(RELAY1, HIGH);
  }
}

void set_relay2 (int state){
  if (state == 1) {
    digitalWrite(RELAY2, LOW);
  } else if (state == 0) {
    digitalWrite(RELAY2, HIGH);
  }
}

void set_relay3 (int state){
  if (state == 1) {
    digitalWrite(RELAY3, LOW);
  } else if (state == 0) {
    digitalWrite(RELAY3, HIGH);
  }
}

void set_relay4 (int state){
  if (state == 1) {
    digitalWrite(RELAY4, LOW);
  } else if (state == 0) {
    digitalWrite(RELAY4, HIGH);
  }
}

void set_ps1_v (int value){
  analogWrite(PS1_V_OUT, value);
}

int get_ps1_v (){
  return analogRead(PS1_V_IN);
}

void set_ps2_v (int value){
  analogWrite(PS2_V_OUT, value);
}

int get_ps2_v (){
  return analogRead(PS2_V_IN);
}

void set_ps1_i (int value){
  analogWrite(PS1_I_OUT, value);
}

int get_ps1_i (){
  return analogRead(PS1_I_IN);
}

void set_ps2_i (int value){
  analogWrite(PS2_I_OUT, value);
}

int get_ps2_i (){
  return analogRead(PS2_I_IN);
}

void dummyFunc(int set_value){
  Serial.println("Called the dummy function!");
}

void setup() {
  // Set up analog reference
  analogReference(EXTERNAL);
  
  Serial.begin(115200);

  // Initialize Com and Error LED's
  pinMode(LED_ERR, OUTPUT);
  pinMode(LED_COM, OUTPUT);
  pinMode(LED_OPEN, OUTPUT);
  pinMode(LED_CLOSED, OUTPUT);
  
  digitalWrite(LED_COM, LOW);
  digitalWrite(LED_ERR, LOW);
  digitalWrite(LED_OPEN, LOW);
  digitalWrite(LED_CLOSED, LOW);

  // Init V and I output PWM's
  pinMode(PS1_V_OUT, OUTPUT);
  pinMode(PS1_I_OUT, OUTPUT);
  pinMode(PS2_V_OUT, OUTPUT);
  pinMode(PS2_I_OUT, OUTPUT);

  // Set them to 0 V
  digitalWrite(PS1_V_OUT, LOW);
  digitalWrite(PS1_I_OUT, LOW);
  digitalWrite(PS2_V_OUT, LOW);
  digitalWrite(PS2_I_OUT, LOW);

  // Init Relay pins
  pinMode(RELAY1, OUTPUT);
  pinMode(RELAY2, OUTPUT);
  pinMode(RELAY3, OUTPUT);
  pinMode(RELAY4, OUTPUT);

  // Set them all to OFF (pulled HIGH)
  digitalWrite(RELAY1, HIGH);
  digitalWrite(RELAY2, HIGH);
  digitalWrite(RELAY3, HIGH);
  digitalWrite(RELAY4, HIGH);
  
  com.add_channel(mist1::Channel("relay1", 'r', 1, &set_relay1, &dummyFunc));
  com.add_channel(mist1::Channel("relay2", 'r', 2, &set_relay2, &dummyFunc));
  com.add_channel(mist1::Channel("relay3", 'r', 3, &set_relay3, &dummyFunc));
  com.add_channel(mist1::Channel("relay4", 'r', 4, &set_relay4, &dummyFunc));

  com.add_channel(mist1::Channel("PS1_V", 'v', 1, &set_ps1_v, &get_ps1_v));
  com.add_channel(mist1::Channel("PS2_V", 'v', 2, &set_ps2_v, &get_ps1_v));
  com.add_channel(mist1::Channel("PS1_I", 'i', 1, &set_ps1_i, &set_ps1_i));
  com.add_channel(mist1::Channel("PS2_I", 'i', 2, &set_ps2_i, &set_ps2_i));
  
}

void loop() {

  // GUI Communication.
  //digitalWrite(LED_COM, LOW);

  if (Serial.available()) {
    
    //digitalWrite(LED_COM, HIGH);
    
    com.respond_to_input_message();

  }  
}

