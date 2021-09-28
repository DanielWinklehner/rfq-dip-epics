#include <Channel.h>
#include <Communication.h>

// Set up serial communication
char inputMessage[128];
mist1::Communication com = mist1::Communication("Ammeter");

#define BNC1 2
#define BNC2 3

long value_1 = 0;
long value_2 = 0;

float curr_1 = 0.0; 
float curr_2 = 0.0;

int samples = 100;
int resolution = 16;
float scaling = 100.0 / (pow(2.0, resolution) * samples);

float get_i_1(){
  value_1 = 0;

  analogRead(BNC1);

  for (int i=0; i<samples; i++){
    value_1 += analogRead(BNC1);
  }

  curr_1 = value_1 * scaling;

  return curr_1;
}

float get_i_2(){
  value_2 = 0;

  analogRead(BNC2);

  for (int i=0; i<samples; i++){
    value_2 += analogRead(BNC2);
  }

  curr_2 = value_2 * scaling;

  return curr_2;
}

void dummyFunc(float set_value){
  //Serial.println("Called the dummy function!");
}

void setup()   { 
  Serial.begin(115200);
  analogReadAveraging(32);
  analogReadResolution(16);
  
  com.add_channel(mist1::Channel("BNC1_CURR", 'i', 1, &dummyFunc, &get_i_1));
  com.add_channel(mist1::Channel("BNC2_CURR", 'i', 2, &dummyFunc, &get_i_2));

}

void loop() {
 
  // GUI Communication.
  if (Serial.available()) {
    
    com.respond_to_input_message();

  } 
}

