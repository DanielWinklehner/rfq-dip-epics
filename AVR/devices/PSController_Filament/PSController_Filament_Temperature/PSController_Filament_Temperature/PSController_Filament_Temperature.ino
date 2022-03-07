//#include <Channel.h>
//#include <Communication.h>
#include <libcom1.hpp>
#include <MAX31856.h>

// A PS Controller for the Filament Power Supplies 
// * PS1 = Filament Heating (blue big guy on bottom)
// 0-5 V on Voltage control, 0-100 mV on Current Control
// * PS2 = Filament Discharge (small guy on top)
// 0-10 V on Voltage Control, 0-10 V on Current Control 

// Set up serial communication
//char inputMessage[128];
//mist1::Communication com = mist1::Communication("TestPSController1");

// Temperature Sensors. 2x.
// The power requirement for the board is less than 2mA.  Most microcontrollers can source or sink a lot more
// than that one each I/O pin.  For example, the ATmega328 supports up to 20mA.  So it is possible to power the
// board using I/O pins for power - so you can turn the board on and off (if you want to).
// FAULT and DRDY are not used by the library (see above)
#define SCK 27
#define SDI 29
#define SDO 31
#define CS1 23
#define CS2 25

// MAX31856 Initial settings (see MAX31856.h and the MAX31856 datasheet)
// The default noise filter is 60Hz, suitable for the USA
#define CR0_INIT  (CR0_AUTOMATIC_CONVERSION + CR0_OPEN_CIRCUIT_FAULT_TYPE_K /* + CR0_NOISE_FILTER_50HZ */)
#define CR1_INIT  (CR1_AVERAGE_2_SAMPLES + CR1_THERMOCOUPLE_TYPE_K)
#define MASK_INIT (~(MASK_VOLTAGE_UNDER_OVER_FAULT + MASK_THERMOCOUPLE_OPEN_FAULT))

// Define pins for error state LED, communication LED
#define LED_ERR 39
#define LED_COM 33
#define LED_OPEN 35
#define LED_CLOSED 37

MAX31856 *temperature1;
MAX31856 *temperature2;

// float t[] = {0.0, 0.0};

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

float get_t1(){
  // return t[0];
  return temperature1->readThermocouple(CELSIUS);
}

float get_t2(){
  // return t[1];
  return temperature2->readThermocouple(CELSIUS);
}

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
  value *= 48.2;
  analogWrite(PS1_V_OUT, value);
}

float get_ps1_v (){
  analogRead(PS1_V_IN);
  int sum10 = 0;
  for (int i = 0; i < 10; i++){
    sum10 += analogRead(PS1_V_IN);
  }
  return sum10 / 1605.4;
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
  value *= 48.2;
  analogWrite(PS1_I_OUT, value);
}

float get_ps1_i (){
  analogRead(PS1_I_IN);
  int sum10 = 0;
  for (int i = 0; i < 10; i++){
    sum10 += analogRead(PS1_I_IN);
  }
  return sum10 / 10.0;
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


using mist1::com1::Channel;
MakeChannelMap(lookup, 9, ({
    Channel{'t', 1, &get_t1, &dummySetFunc},
    Channel{'t', 2, &get_t2, &dummySetFunc},
    Channel{'o', 1, &dummyGetFunc, &set_ps1_on},
    Channel{'o', 2, &dummyGetFunc, &set_ps2_on},
    Channel{'v', 1, &get_ps1_v, &set_ps1_v},
    Channel{'v', 2, &get_ps2_v, &set_ps2_v},
    Channel{'i', 1, &get_ps1_i, &set_ps1_i},
    Channel{'i', 2, &get_ps2_i, &set_ps2_i},
    Channel{'x', 1, &get_ext_ilk, &dummySetFunc},
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

mist1::com1::SerialDevice<128, 9> device(io_ctx, lookup);


void setup() {
  Serial.begin(115200);

  //delay(10);

  // Set up analog reference
  analogReference(EXTERNAL);
  
  // Define the pins used to communicate with the MAX31856
  temperature1 = new MAX31856(SDI, SDO, CS1, SCK);
  temperature2 = new MAX31856(SDI, SDO, CS2, SCK);
  
  // Initializing the MAX31855's registers
  temperature1->writeRegister(REGISTER_CR0, CR0_INIT);
  temperature1->writeRegister(REGISTER_CR1, CR1_INIT);
  temperature1->writeRegister(REGISTER_MASK, MASK_INIT);

  temperature2->writeRegister(REGISTER_CR0, CR0_INIT);
  temperature2->writeRegister(REGISTER_CR1, CR1_INIT);
  temperature2->writeRegister(REGISTER_MASK, MASK_INIT);

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
  /*
  com.add_channel(mist1::Channel("TEMP1", 't', 1, &dummySetFunc, &get_t1));
  com.add_channel(mist1::Channel("TEMP2", 't', 2, &dummySetFunc, &get_t2));
  com.add_channel(mist1::Channel("FIL_CUR_ON", 'o', 1, &set_ps1_on, &dummyGetFunc));
  com.add_channel(mist1::Channel("FIL_DCHRG_ON", 'o', 2, &set_ps2_on, &dummyGetFunc));
  com.add_channel(mist1::Channel("FIL_CUR_V", 'v', 1, &set_ps1_v, &get_ps1_v));
  com.add_channel(mist1::Channel("FIL_DCHRG_V", 'v', 2, &set_ps2_v, &get_ps2_v));
  com.add_channel(mist1::Channel("FIL_CUR_I", 'i', 1, &set_ps1_i, &get_ps1_i));
  com.add_channel(mist1::Channel("FIL_DCHRG_I", 'i', 2, &set_ps2_i, &get_ps2_i));
  com.add_channel(mist1::Channel("EXT_ILK", 'x', 1, &dummySetFunc, &get_ext_ilk));  //To read interlock status
  */
}

void loop() {
  // Read out temperature sensors
  // t[0] = temperature1->readThermocouple(CELSIUS);
  // t[1] = temperature2->readThermocouple(CELSIUS);

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
    
    //com.respond_to_input_message();
    device.communicate();
  }  
}
