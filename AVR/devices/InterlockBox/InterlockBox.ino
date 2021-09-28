//#include <Channel.h>
#include <stdio.h>
#include <libcom1.hpp>

// Set up serial communication
char inputMessage[128];
//mist1::Communication com = mist1::Communication("Sensor Box");

volatile int com_flag = 0;

// Solenoid Valve Variables (Relays). x2.
const int solenoidValvePins[] = {26, 24}; // (relay 1 and 4 are unused on board.)
bool solenoidValveValues[] = {HIGH, HIGH}; // Relays are closed when pulled to ground. Default should be open (HIGH).

// Micro Switches for interlocks. x2.
const int microSwitchPins[] = {2, 3}; 
bool microSwitchValues[] = {LOW, LOW};

// Vacuum Valves. x2.
const int vacuumValvePins[] = {21, 20, 19, 18};
bool vacuumValveMicroSwitchValues[] = {LOW, LOW, LOW, LOW};
bool vacuumValveValues[] = {LOW, LOW};  // For each vacuum valve, two microswitches determine whether or not it's open.

// Define pins for error state LED, communication LED
#define LED_ERR 12
#define LED_COM 13
#define LED_INTLK_OPEN 11
#define LED_INTLK_CLOSED 10

float get_interlock1(){
  return (float)microSwitchValues[0];
}

float get_interlock2(){
  return (float)microSwitchValues[1];
}

void set_solenoid1(float set_value){
  if (set_value == 1.0) {
    solenoidValveValues[0] = LOW;
    digitalWrite(solenoidValvePins[0], LOW);
  } else if (set_value = 0.0) {
    solenoidValveValues[0] = HIGH;
    digitalWrite(solenoidValvePins[0], HIGH);
  }
}

void set_solenoid2(float set_value){
  if (set_value == 1.0) {
    solenoidValveValues[1] = LOW;
    digitalWrite(solenoidValvePins[1], LOW);
  } else if (set_value = 0.0) {
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

using mist1::com1::Channel;
MakeChannelMap(lookup, 4, ({
    Channel{ 'i', 1, &get_interlock1, &dummySetFunc},
    Channel{ 'i', 2, &get_interlock2, &dummySetFunc},
    Channel{ 's', 1, &dummyGetFunc, &set_solenoid1},
    Channel{ 's', 2, &dummyGetFunc, &set_solenoid2}
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

mist1::com1::SerialDevice<128, 4> device(io_ctx, lookup);

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
  
  // Vacuum Valves.
  for (unsigned i = 0; i < sizeof(vacuumValvePins) / sizeof(int); i++) {
    pinMode(vacuumValvePins[i], INPUT);
  }
  
  // Microswitches.
  for (unsigned i = 0; i < sizeof(microSwitchPins) / sizeof(int); i++) {
    pinMode(microSwitchPins[i], INPUT);
  }
    
  Serial.begin(115200);

  //com.add_channel(mist1::Channel("INTERLOCK1", 'i', 1, &dummySetFunc, &get_interlock1));
  //com.add_channel(mist1::Channel("INTERLOCK2", 'i', 2, &dummySetFunc, &get_interlock2));
  //com.add_channel(mist1::Channel("SOLENOID1", 's', 1, &set_solenoid1, &dummyGetFunc));
  //com.add_channel(mist1::Channel("SOLENOID2", 's', 2, &set_solenoid2, &dummyGetFunc));
 
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
  for (unsigned i = 0; i < sizeof(microSwitchPins) / sizeof(int); i++) {
    microSwitchValues[i] = digitalRead(microSwitchPins[i]);
  }

  // GUI Communication.
  digitalWrite(LED_COM, LOW);
  if (Serial.available()) {
    digitalWrite(LED_COM, HIGH);
    device.communicate();
  }  
}
