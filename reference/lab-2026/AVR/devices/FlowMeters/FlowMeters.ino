//#include <Channel.h>
//#include <Communication.h>
#include <libcom1.hpp>

// Set up serial communication
//char inputMessage[128];
//mist1::Communication com = mist1::Communication("Sensor Box");

#include <MAX31856.h>

// Flow meters. x5.
const int flowSensorPins[] = {A2, A3, A4, A5, A6};
volatile int flowSensorFreqs[] = {0, 0, 0, 0, 0};
float flowSensorFreqsWrite[] = {0.0, 0.0, 0.0, 0.0, 0.0};
unsigned long currentTime;
unsigned long cloopTime;

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
MakeChannelMap(lookup, 5, ({
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

mist1::com1::SerialDevice<128, 5> device(io_ctx, lookup);


void setup()   { 
  // Init Com and Error LED's
  pinMode(LED_RESET, OUTPUT);
  pinMode(LED_USER, OUTPUT);
  digitalWrite(LED_RESET, LOW);
  digitalWrite(LED_USER, LOW);
  
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
      
      flowSensorFreqsWrite[i] = (float)flowSensorFreqs[i] * 0.095238; //(1260 pulses per l, 60 s in a min, measuring for 0.5 s)
      flowSensorFreqs[i] = 0; // Reset counter.
    }
  }

  // GUI Communication.
  digitalWrite(LED_USER, LOW);

  if (Serial.available() > 0) {
    
    digitalWrite(LED_USER, HIGH);
    
    //com.respond_to_input_message();
    device.communicate();
  }   
}
