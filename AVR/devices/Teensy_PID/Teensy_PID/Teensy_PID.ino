//#include <Channel.h>
//#include <Communication.h>
#include <libcom1.hpp>

// A PS Controller for the HV Power Supplies
// * PS1 = Glassman, Einzel Lens, Lower Row of BNC's
// 0-10 V on Voltage control, 0-10 V on Current Control
// * PS2 = Farnell HiVolt, Ion Source HV, Upper Row of BNC's
// 0-10 V on Voltage Control, 0-10 V on Current Control

// Set up serial communication
//char inputMessage[128];
//mist1::Communication com = mist1::Communication("HVPSController");

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

using mist1::com1::Channel;
MakeChannelMap(lookup, 1, ({
    Channel{ 'v', 1, &get_tsy_v, &set_tsy_v},
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

mist1::com1::SerialDevice<128, 1> device(io_ctx, lookup);

void setup() {
  Serial.begin(115200);

  // Init V and I output PWM's
  pinMode(TSY_V_OUT, OUTPUT);

  // Set them to 0 V
  analogWrite(TSY_V_OUT, 0);;
  
  //com.add_channel(mist1::Channel("HV_GLAS_V", 'v', 1, &set_tsy_v, &get_tsy_v));
 
}

void loop() {
  
  // GUI Communication.

  if (Serial.available()) {
 
    //com.respond_to_input_message();
    device.communicate();
  }  
}

