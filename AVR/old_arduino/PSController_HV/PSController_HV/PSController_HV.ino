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

// Define pins for relays (PS on/off, PS interlock)
#define PS1_ON 14
#define PS1_ILK 15
#define PS2_ON 16
#define PS2_ILK 17

//Define External Interlock Pin
#define EXT_ILK 21

//Define interlock open/closed
#define CLOSED 1
#define OPEN 0

// Set up interlock switch debounce time
long debouncing_time = 150; //Debouncing Time in Milliseconds
volatile unsigned long last_micros;

volatile unsigned int error_state = 0;
volatile unsigned int interlock_state = OPEN;

void set_ps1_on (float state){
  if (state == 1.0) {
    digitalWrite(PS1_ON, LOW);
  } else if (state == 0.0) {
    digitalWrite(PS1_ON, HIGH);
  }
}

void set_ps2_on (float state){
  if (state == 1.0) {
    digitalWrite(PS2_ON, LOW);
  } else if (state == 0.0) {
    digitalWrite(PS2_ON, HIGH);
  }
}

void set_ps1_v (float value){
  value *= 24.1;
  analogWrite(PS1_V_OUT, value);
}

float get_ps1_v (){
  analogRead(PS1_V_IN);
  int sum10 = 0;
  for (int i = 0; i < 10; i++){
    sum10 += analogRead(PS1_V_IN);
  }
  return sum10 / 852.7;
}

void set_ps2_v (float value){
  value *= 24.1;
  analogWrite(PS2_V_OUT, value);
}

float get_ps2_v (){
  analogRead(PS2_V_IN);
  int sum10 = 0;
  for (int i = 0; i < 10; i++){
    sum10 += analogRead(PS2_V_IN);
  }
  return sum10 / 852.7;
}

void set_ps1_i (float value){
  value *= 24.1;
  analogWrite(PS1_I_OUT, value);
}

float get_ps1_i (){
  analogRead(PS1_I_IN);
  int sum10 = 0;
  for (int i = 0; i < 10; i++){
    sum10 += analogRead(PS1_I_IN);
  }
  return sum10 / 852.7;
}

void set_ps2_i (float value){
  value *= 24.1;
  analogWrite(PS2_I_OUT, value);
}

float get_ps2_i (){
  analogRead(PS2_I_IN);
  int sum10 = 0;
  for (int i = 0; i < 10; i++){
    sum10 += analogRead(PS2_I_IN);
  }
  return sum10 / 852.7;
}

float get_ext_ilk(){
  return (float) interlock_state;
}

void dummySetFunc(float set_value){
  //Serial.println("Called the dummy function!");
}

float dummyGetFunc(){
  //Serial.println("Called the dummy function!");
}

void setup() {
  Serial.begin(115200);

  // Set up analog reference
  analogReference(EXTERNAL);

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
  pinMode(PS1_ON, OUTPUT);
  pinMode(PS2_ON, OUTPUT);
  pinMode(PS1_ILK, OUTPUT);
  pinMode(PS2_ILK, OUTPUT);

  // Set them all to OFF (pulled HIGH)
  digitalWrite(PS1_ON, HIGH);
  digitalWrite(PS2_ON, HIGH);
  digitalWrite(PS1_ILK, HIGH);
  digitalWrite(PS2_ILK, HIGH);

  // Init External Interlock Pin
  pinMode(EXT_ILK, INPUT);
  
  com.add_channel(mist1::Channel("HV_GLAS_ON", 'o', 1, &set_ps1_on, &dummyGetFunc));
  com.add_channel(mist1::Channel("HV_FARN_ON", 'o', 2, &set_ps2_on, &dummyGetFunc));
  com.add_channel(mist1::Channel("HV_GLAS_V", 'v', 1, &set_ps1_v, &get_ps1_v));
  com.add_channel(mist1::Channel("HV_FARN_V", 'v', 2, &set_ps2_v, &get_ps2_v));
  com.add_channel(mist1::Channel("HV_GLAS_I", 'i', 1, &set_ps1_i, &get_ps1_i));
  com.add_channel(mist1::Channel("HV_FARN_I", 'i', 2, &set_ps2_i, &get_ps2_i));
  com.add_channel(mist1::Channel("EXT_ILK", 'x', 1, &dummySetFunc, &get_ext_ilk));  //To read interlock status
}

void loop() {

  if (digitalRead(EXT_ILK) == HIGH){
    digitalWrite(PS1_ILK, HIGH);
    digitalWrite(PS2_ILK, HIGH);
    digitalWrite(LED_CLOSED, LOW);
    digitalWrite(LED_OPEN, HIGH);
    interlock_state = OPEN;
  } else {
    digitalWrite(PS1_ILK, LOW);
    digitalWrite(PS2_ILK, LOW);
    digitalWrite(LED_CLOSED, HIGH);
    digitalWrite(LED_OPEN, LOW);
    interlock_state = CLOSED;
  }

  // GUI Communication.
  digitalWrite(LED_COM, LOW);

  if (Serial.available()) {
    
    digitalWrite(LED_COM, HIGH);
    
    com.respond_to_input_message();

  }  
}

