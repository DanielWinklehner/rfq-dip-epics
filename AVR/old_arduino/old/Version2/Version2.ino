#include "Communication.h"

#define MYPIN1 50
#define MYPIN2 51

char message[128];
mist1::Communication com = mist1::Communication();


void set_value1(float state){

  Serial.print("Setting value of PIN1 to ");
  Serial.println(state);
  
  if (state == 1.) {
    digitalWrite(MYPIN1, HIGH);
  } else if (state == 0.) {
    digitalWrite(MYPIN1, LOW);
  }
}

void set_value2(float state){

  Serial.print("Setting value of PIN2 to ");
  Serial.println(state);
  
  if (state == 1.) {
    digitalWrite(MYPIN2, HIGH);
  } else if (state == 0.) {
    digitalWrite(MYPIN2, LOW);
  }
}

float get_value1() {
  return digitalRead(MYPIN1);
}

float get_value2() {
  return digitalRead(MYPIN2);
}


void setup() {
  Serial.begin(115200);
  
  com.add_channel(mist1::Channel("channel1", 'h', 1, & set_value1, & get_value1));
  com.add_channel(mist1::Channel("channel2", 'h', 2, & set_value2, & get_value2));

  
}

void loop() {

    //com.get_serial_data(message);
    //Serial.print("I am giving you: ");
    //Serial.println(message);

    //Serial.println(com.get_all_channel_names());

    com.respond_to_input_message();

}
