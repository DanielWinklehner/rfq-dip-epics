//#include <Channel.h>
//#include <Communication.h>
#include <libcom1.hpp>

// Set up serial communication
//char inputMessage[128];
//mist1::Communication com = mist1::Communication("Sensor Box");

#include <MAX31856.h>

// Flow meters. x5.
const int flowSensorPins[] = {18, 19, 20, 3, 2};
volatile int flowSensorFreqs[] = {0, 0, 0, 0, 0};
float flowSensorFreqsWrite[] = {0.0, 0.0, 0.0, 0.0, 0.0};
unsigned long currentTime;
unsigned long cloopTime;

// Temperature Sensors. 8x.
// The power requirement for the board is less than 2mA.  Most microcontrollers can source or sink a lot more
// than that one each I/O pin.  For example, the ATmega328 supports up to 20mA.  So it is possible to power the
// board using I/O pins for power - so you can turn the board on and off (if you want to).
// FAULT and DRDY are not used by the library (see above)
#define SCK1    44
#define SDI1    42
#define SDO1    40

#define SCK2    49
#define SDI2    51
#define SDO2    53

#define CS1    46
#define CS2    48
#define CS3    50
#define CS4    52
#define CS5    47
#define CS6    45
#define CS7    43
#define CS8    41

// Define pins for error state LED, communication LED
#define LED_ERR 12
#define LED_COM 13

// MAX31856 Initial settings (see MAX31856.h and the MAX31856 datasheet)
// The default noise filter is 60Hz, suitable for the USA
#define CR0_INIT  (CR0_AUTOMATIC_CONVERSION + CR0_OPEN_CIRCUIT_FAULT_TYPE_K /* + CR0_NOISE_FILTER_50HZ */)
#define CR1_INIT  (CR1_AVERAGE_2_SAMPLES + CR1_THERMOCOUPLE_TYPE_K)
#define MASK_INIT (~(MASK_VOLTAGE_UNDER_OVER_FAULT + MASK_THERMOCOUPLE_OPEN_FAULT))

MAX31856 *temperature1;
MAX31856 *temperature2;
MAX31856 *temperature3;
MAX31856 *temperature4;
MAX31856 *temperature5;
MAX31856 *temperature6;
MAX31856 *temperature7;
//MAX31856 *temperature8;

float t[] = {0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0};

// Who named these?
float get_t1(){
  return t[0];
}

float get_t2(){
  return t[1];
}

float get_t3(){
  return t[2];
}

float get_t4(){
  return t[3];
}

float get_t5(){
  return t[4];
}

float get_t6(){
  return t[5];
}

float get_t7(){
  return t[6];
}

float get_flow1(){
  return flowSensorFreqsWrite[0];
}

float get_flow2(){
  return flowSensorFreqsWrite[1];
}

float get_flow3(){
  return flowSensorFreqsWrite[2];
}

float get_flow4(){
  return flowSensorFreqsWrite[3];
}

float get_flow5(){
  return flowSensorFreqsWrite[4];
}

void dummySetFunc(float set_value){
  //Serial.println("Called the dummy function!");
}

using mist1::com1::Channel;
MakeChannelMap(lookup, 12, ({
    Channel{'t', 1, &get_t1, &dummySetFunc},
    Channel{'t', 2, &get_t2, &dummySetFunc},
    Channel{'t', 3, &get_t3, &dummySetFunc},
    Channel{'t', 4, &get_t4, &dummySetFunc},
    Channel{'t', 5, &get_t5, &dummySetFunc},
    Channel{'t', 6, &get_t6, &dummySetFunc},
    Channel{'t', 7, &get_t7, &dummySetFunc},
    Channel{'f', 1, &get_flow1, &dummySetFunc},
    Channel{'f', 2, &get_flow2, &dummySetFunc},
    Channel{'f', 3, &get_flow3, &dummySetFunc},
    Channel{'f', 4, &get_flow4, &dummySetFunc},
    Channel{'f', 5, &get_flow5, &dummySetFunc},
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

mist1::com1::SerialDevice<128, 12> device(io_ctx, lookup);


void setup()   { 
  // Init Com and Error LED's
  pinMode(LED_ERR, OUTPUT);
  pinMode(LED_COM, OUTPUT);
  digitalWrite(LED_COM, LOW);
  digitalWrite(LED_ERR, LOW);
  
  // Flow Meters.
  for (unsigned i = 0; i < sizeof(flowSensorPins) / sizeof(int); i++) {
    pinMode(flowSensorPins[i], INPUT);
    // Activate the pullup resistor
    digitalWrite(flowSensorPins[i], HIGH);
  }

  Serial.begin(115200); // 115200

  // Interrupts for flow sensors.
  attachInterrupt(digitalPinToInterrupt(flowSensorPins[0]), flow_interrupt0, RISING);
  attachInterrupt(digitalPinToInterrupt(flowSensorPins[1]), flow_interrupt1, RISING);
  attachInterrupt(digitalPinToInterrupt(flowSensorPins[2]), flow_interrupt2, RISING);
  attachInterrupt(digitalPinToInterrupt(flowSensorPins[3]), flow_interrupt3, RISING);
  attachInterrupt(digitalPinToInterrupt(flowSensorPins[4]), flow_interrupt4, RISING);

  // Define the pins used to communicate with the MAX31856
  temperature1 = new MAX31856(SDI1, SDO1, CS1, SCK1);
  temperature2 = new MAX31856(SDI1, SDO1, CS2, SCK1);
  temperature3 = new MAX31856(SDI1, SDO1, CS3, SCK1);
  temperature4 = new MAX31856(SDI1, SDO1, CS4, SCK1);
  temperature5 = new MAX31856(SDI2, SDO2, CS5, SCK2);
  temperature6 = new MAX31856(SDI2, SDO2, CS6, SCK2);
  temperature7 = new MAX31856(SDI2, SDO2, CS7, SCK2);
//  temperature8 = new MAX31856(SDI2, SDO2, CS8, SCK2);
  
  // Initializing the MAX31855's registers
  temperature1->writeRegister(REGISTER_CR0, CR0_INIT);
  temperature1->writeRegister(REGISTER_CR1, CR1_INIT);
  temperature1->writeRegister(REGISTER_MASK, MASK_INIT);

  temperature2->writeRegister(REGISTER_CR0, CR0_INIT);
  temperature2->writeRegister(REGISTER_CR1, CR1_INIT);
  temperature2->writeRegister(REGISTER_MASK, MASK_INIT);

  temperature3->writeRegister(REGISTER_CR0, CR0_INIT);
  temperature3->writeRegister(REGISTER_CR1, CR1_INIT);
  temperature3->writeRegister(REGISTER_MASK, MASK_INIT);

  temperature4->writeRegister(REGISTER_CR0, CR0_INIT);
  temperature4->writeRegister(REGISTER_CR1, CR1_INIT);
  temperature4->writeRegister(REGISTER_MASK, MASK_INIT);

  temperature5->writeRegister(REGISTER_CR0, CR0_INIT);
  temperature5->writeRegister(REGISTER_CR1, CR1_INIT);
  temperature5->writeRegister(REGISTER_MASK, MASK_INIT);

  temperature6->writeRegister(REGISTER_CR0, CR0_INIT);
  temperature6->writeRegister(REGISTER_CR1, CR1_INIT);
  temperature6->writeRegister(REGISTER_MASK, MASK_INIT);

  temperature7->writeRegister(REGISTER_CR0, CR0_INIT);
  temperature7->writeRegister(REGISTER_CR1, CR1_INIT);
  temperature7->writeRegister(REGISTER_MASK, MASK_INIT);

//  temperature8->writeRegister(REGISTER_CR0, CR0_INIT);
//  temperature8->writeRegister(REGISTER_CR1, CR1_INIT);
//  temperature8->writeRegister(REGISTER_MASK, MASK_INIT);
  /*
  com.add_channel(mist1::Channel("TEMP1", 't', 1, &dummyFunc, &get_t1));
  com.add_channel(mist1::Channel("TEMP2", 't', 2, &dummyFunc, &get_t2));
  com.add_channel(mist1::Channel("TEMP3", 't', 3, &dummyFunc, &get_t3));
  com.add_channel(mist1::Channel("TEMP4", 't', 4, &dummyFunc, &get_t4));
  com.add_channel(mist1::Channel("TEMP5", 't', 5, &dummyFunc, &get_t5));
  com.add_channel(mist1::Channel("TEMP6", 't', 6, &dummyFunc, &get_t6));
  com.add_channel(mist1::Channel("TEMP7", 't', 7, &dummyFunc, &get_t7));

  com.add_channel(mist1::Channel("FLOW1", 'f', 1, &dummyFunc, &get_flow1));
  com.add_channel(mist1::Channel("FLOW2", 'f', 2, &dummyFunc, &get_flow2));
  com.add_channel(mist1::Channel("FLOW3", 'f', 3, &dummyFunc, &get_flow3));
  com.add_channel(mist1::Channel("FLOW4", 'f', 4, &dummyFunc, &get_flow4));
  com.add_channel(mist1::Channel("FLOW5", 'f', 5, &dummyFunc, &get_flow5));
  */
}

void flow_interrupt0() {
  flowSensorFreqs[0]++;
}

void flow_interrupt1() {
  flowSensorFreqs[1]++;
}

void flow_interrupt2() {
  flowSensorFreqs[2]++;
}

void flow_interrupt3() {
  flowSensorFreqs[3]++;
}

void flow_interrupt4() {
  flowSensorFreqs[4]++;
}

void loop() {
  // Get the current time in milliseconds
  currentTime = millis();
  
  // Every half second, calculate and print litres/hour, and read temperatures
  // The temperatures can be moved into their own if clause to read them 
  // out more often.
  if(currentTime >= (cloopTime + 500)) {
    
    cloopTime = currentTime; // Updates cloopTime
    // Read Flow Meters.
    
    for (unsigned i = 0; i < sizeof(flowSensorPins) / sizeof(int); i++) {
      flowSensorFreqsWrite[i] = (float)flowSensorFreqs[i] * 0.06; //(1000 pulses per l, 60 s in a min, measuring for 0.5 s)
      flowSensorFreqs[i] = 0; // Reset counter.
    }
    // Temperature sensors (read out every half second for now)
    t[0] = temperature1->readThermocouple(CELSIUS);
    t[1] = temperature2->readThermocouple(CELSIUS);
    t[2] = temperature3->readThermocouple(CELSIUS);
    t[3] = temperature4->readThermocouple(CELSIUS);
    t[4] = temperature5->readThermocouple(CELSIUS);
    t[5] = temperature6->readThermocouple(CELSIUS);
    t[6] = temperature7->readThermocouple(CELSIUS);
    // t[7] = temperature8->readThermocouple(CELSIUS);
  }

  // GUI Communication.
  digitalWrite(LED_COM, LOW);

  if (Serial.available() > 0) {
    
    digitalWrite(LED_COM, HIGH);
    
    //com.respond_to_input_message();
    device.communicate();
  }   
}
