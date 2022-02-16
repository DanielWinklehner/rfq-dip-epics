#include <Channel.h>
#include <Communication.h>

// Set up serial communication
char inputMessage[128];
mist1::Communication com = mist1::Communication("Sensor Box");

volatile int com_flag = 0;

// Solenoid Valve Variables (Relays). x2.
const int solenoidValvePins[] = {26, 24}; //
bool solenoidValveValues[] = {HIGH, HIGH}; // Relays are closed when pulled to ground. Default should be open (HIGH).

const int interlockOutPins[] = {28, 22}; //
bool interlockOutValues[] = {HIGH, HIGH}; // Relays are closed when pulled to ground. Default should be open (HIGH).

// Micro Switches for interlocks. x2.
const int interlockInPins[] = {2, 3}; 
bool interlockInValues[] = {LOW, LOW};

// Vacuum Valves. x2.
const int vacuumValvePins[] = {7, 6, 5, 4};
bool vacuumValveMicroSwitchValues[] = {LOW, LOW, LOW, LOW};
bool vacuumValveValues[] = {LOW, LOW};  // For each vacuum valve, two microswitches determine whether or not it's open.

// Define pins for error state LED, communication LED
#define LED_ERR 12
#define LED_COM 13
#define LED_INTLK_OPEN 11
#define LED_INTLK_CLOSED 10

float get_interlock1(){
  return (float)interlockInValues[0];
}

float get_interlock2(){
  return (float)interlockInValues[1];
}

void set_solenoid1(float set_value){
  if (set_value == 1.0) {
    solenoidValveValues[0] = LOW;
    digitalWrite(solenoidValvePins[0], LOW);
  } else {
    solenoidValveValues[0] = HIGH;
    digitalWrite(solenoidValvePins[0], HIGH);
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

void dummySetFunc(float set_value){
  //Serial.println("Called the dummy function!");
}

float dummyGetFunc(){
  //Serial.println("Called the dummy function!");
}

void setup()   { 
  // Init Com and Error LED's
  pinMode(LED_ERR, OUTPUT);
  pinMode(LED_COM, OUTPUT);
  digitalWrite(LED_COM, LOW);
  digitalWrite(LED_ERR, LOW);

  // Init Interlock LED's
  pinMode(LED_INTLK_OPEN, OUTPUT);
  pinMode(LED_INTLK_CLOSED, OUTPUT);
  digitalWrite(LED_INTLK_OPEN, HIGH);
  digitalWrite(LED_INTLK_CLOSED, LOW);
  
  // Initialise the Arduino data pins.

  // Solenoid Valves.
  for (unsigned i = 0; i < sizeof(solenoidValvePins) / sizeof(int); i++) {
    pinMode(solenoidValvePins[i], OUTPUT);
    digitalWrite(solenoidValvePins[i], HIGH);
  }
  
  // Vacuum Valves.
  for (unsigned i = 0; i < sizeof(vacuumValvePins) / sizeof(int); i++) {
    pinMode(vacuumValvePins[i], INPUT);
  }
  
  // Interlock Input
  for (unsigned i = 0; i < sizeof(interlockInPins) / sizeof(int); i++) {
    pinMode(interlockInPins[i], INPUT);
  }

  //Interlock Output
  for (unsigned i = 0; i < sizeof(interlockOutPins) / sizeof(int); i++) {
    pinMode(interlockOutPins[i], OUTPUT);
    digitalWrite(interlockOutPins[i], HIGH);
  }
    
  Serial.begin(115200);

  com.add_channel(mist1::Channel("INTERLOCK1", 'i', 1, &dummySetFunc, &get_interlock1));
  com.add_channel(mist1::Channel("INTERLOCK2", 'i', 2, &dummySetFunc, &get_interlock2));
  com.add_channel(mist1::Channel("SOLENOID1", 's', 1, &set_solenoid1, &dummyGetFunc));
  com.add_channel(mist1::Channel("SOLENOID2", 's', 2, &set_solenoid2, &dummyGetFunc));
 
}

void loop() {  

  // Read Vacuum Valves.
  for (unsigned i = 0; i < sizeof(vacuumValvePins) / sizeof(int); i++) {
    vacuumValveMicroSwitchValues[i] = digitalRead(vacuumValvePins[i]);
  }

  // Determine whether each of the two vacuum valves are open or not based on the 4 microswitch values.
  // Whether or not a vacuum valve is open depends on the values of two of its associated microswitches.
  for (unsigned i = 0; i < sizeof(vacuumValvePins) / sizeof(int) - 1; i++) {
    if ( (vacuumValveMicroSwitchValues[i]) & ( ! vacuumValveMicroSwitchValues[i + 1] ) ) {
      // Valve is closed.
      vacuumValveValues[((int) (i / 2))] = LOW;
    }
    else if ( ( ! vacuumValveMicroSwitchValues[i]) & (vacuumValveMicroSwitchValues[i + 1] ) ) {
      // Valve is open.
      vacuumValveValues[((int) (i / 2))] = HIGH;
    }
    else {
      // Error State.
    }
  }
  
  // Read Micro Switches.
  for (unsigned i = 0; i < sizeof(interlockInPins) / sizeof(int); i++) {
    interlockInValues[i] = digitalRead(interlockInPins[i]);
  }

  if ( (interlockInValues[0] == HIGH) && (interlockInValues[1] == HIGH)){
    // Interlock is CLOSED
    digitalWrite(LED_INTLK_OPEN, LOW);
    digitalWrite(LED_INTLK_CLOSED, HIGH);
    digitalWrite(interlockOutPins[0], LOW);
    digitalWrite(interlockOutPins[1], LOW);
  } else {
    // Interlock is OPEN
    digitalWrite(LED_INTLK_OPEN, HIGH);
    digitalWrite(LED_INTLK_CLOSED, LOW);
    digitalWrite(interlockOutPins[0], HIGH);
    digitalWrite(interlockOutPins[1], HIGH);
  }

  // GUI Communication.
  digitalWrite(LED_COM, LOW);

  if (Serial.available()) {
    
    digitalWrite(LED_COM, HIGH);
    
    com.respond_to_input_message();

  }
}

