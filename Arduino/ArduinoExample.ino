#include <Channel.h>
#include <Communication.h>

// A simple Arduino program that uses the communication_library and
// returns 4 channels of sine waves. the user can also set LED 13 on and off
// requires Arduino Mega 2560. Connect an LED between pin 12 and GND.

// Set up serial communication
char inputMessage[128];
mist1::Communication com = mist1::Communication("Test Box");


// Four frequencies for the sine waves
const float frequencies[] = {0.1/1000.0*2.0*PI, 0.2/1000.0*2.0*PI, 0.4/1000.0*2.0*PI, 0.8/1000.0*2.0*PI};  // Hz/1000.0*2*pi

// The LED to turn on/off remotely
#define LED_BLINK 12
// A com LED which will be flashing (or appear to be on if polling rate is high)
#define LED_COM 13

// The communication_library links each channel to predefined set and get functions
float get_s1(){
  return sin(frequencies[0] * millis());
}

float get_s2(){
  return sin(frequencies[1]* millis());
}

float get_s3(){
  return sin(frequencies[2] * millis());
}

float get_s4(){
  return sin(frequencies[3] * millis());
}

// A set function to switch LED_BLINK from on to off and vice versa
void set_led(float set_value){
  if (set_value == 1.0)
    digitalWrite(LED_BLINK, HIGH);
  else
    digitalWrite(LED_BLINK, LOW);
}

// A dummy set function 
void dummySetFunc(float set_value){
  //Serial.println("Called the dummy set function!");
}

// A dummy get function 
float dummyGetFunc(){
  //Serial.println("Called the dummy get function!");
  return 0.0;
}

void setup() {
  // put your setup code here, to run once:
  
  // init com and blink LED's
  pinMode(LED_BLINK, OUTPUT);
  pinMode(LED_COM, OUTPUT);
  digitalWrite(LED_BLINK, LOW);
  digitalWrite(LED_COM, LOW);
  
  // init Serial communications
  Serial.begin(115200); // Baud rate 115200 

  // Now we add the four read channels for the sine waves (note that the set channel is
  // just connected to the dummy function for each channel)
  com.set_delay_us(75);
  com.add_channel(mist1::Channel("Sine1", 's', 1, &dummySetFunc, &get_s1));
  com.add_channel(mist1::Channel("Sine2", 's', 2, &dummySetFunc, &get_s2));
  com.add_channel(mist1::Channel("Sine3", 's', 3, &dummySetFunc, &get_s3));
  com.add_channel(mist1::Channel("Sine4", 's', 4, &dummySetFunc, &get_s4));
  com.add_channel(mist1::Channel("LED1", 'l', 1, &set_led, &dummyGetFunc));
}

void loop() {
  // put your main code here, to run repeatedly:
  
  // GUI Communication.
  digitalWrite(LED_COM, LOW);

  if (Serial.available() > 0) {
    
    digitalWrite(LED_COM, HIGH);
    
    com.respond_to_input_message();
  }
}
