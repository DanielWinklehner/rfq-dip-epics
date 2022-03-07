#include <Channel.h>
#include <Communication.h>

char inputMessage[128];
mist1::Communication com = mist1::Communication("Test Box");

float ret_a1() {return 0.0f;}
float ret_a2() {return 1.0f;}
float ret_b3() {return -2.0f;}
float ret_b4() {return 3.141592f;} // pi
float ret_c5() {return 2.718282f;} // e
float ret_c1() {return 1.618034f;} // phi
float ret_d2() {return 1.414214f;} // sqrt(2)
float ret_d3() {return 0.693147f;} // ln 2
float ret_e4() {return 123.4567f;}
float ret_e5() {return -1234567.0f;}

void dummy_set(float setval) {
  // Here b/c the setter doesn't return anything, but the benchmark needs feedback
  Serial.print("o\n");  
}

void setup() {
  Serial.begin(115200);

  com.set_delay_us(70);
  com.add_channel(mist1::Channel("a1", 'a', 1, &dummy_set, &ret_a1));
  com.add_channel(mist1::Channel("a2", 'a', 2, &dummy_set, &ret_a2));
  com.add_channel(mist1::Channel("b3", 'b', 3, &dummy_set, &ret_b3));
  com.add_channel(mist1::Channel("b4", 'b', 4, &dummy_set, &ret_b4));
  com.add_channel(mist1::Channel("c5", 'c', 5, &dummy_set, &ret_c5));
  com.add_channel(mist1::Channel("c1", 'c', 1, &dummy_set, &ret_c1));
  com.add_channel(mist1::Channel("d2", 'd', 2, &dummy_set, &ret_d2));
  com.add_channel(mist1::Channel("d3", 'd', 3, &dummy_set, &ret_d3));
  com.add_channel(mist1::Channel("e4", 'e', 4, &dummy_set, &ret_e4));
  com.add_channel(mist1::Channel("e5", 'e', 5, &dummy_set, &ret_e5));
}

unsigned long tot_time = 0;
unsigned iter = 0;

void loop() {
  if (Serial.available() > 0) {
    iter += 1;
    unsigned long time_a = micros();
    com.respond_to_input_message();
    tot_time += ( micros() - time_a );
  }

  if (iter == 1000) {
    Serial.print("EOF\nCompleted 1000 iterations in: ");
    Serial.print(tot_time);
    Serial.print(" us\n");
    Serial.flush();
    tot_time = 0;
    iter = 0;
  }
}
