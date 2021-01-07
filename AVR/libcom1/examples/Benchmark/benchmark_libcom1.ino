#include <stdio.h>
#include <libcom1.hpp>

#define ENABLE_PRINTF 0

#if ENABLE_PRINTF
PRINTF_SERIAL_PREINIT();
#endif

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

using mist1::com1::Channel;

MakeChannelMap(lookup, 10, ({
    Channel{ 'a', 1, &ret_a1, &dummy_set },
    Channel{ 'a', 2, &ret_a2, &dummy_set },
    Channel{ 'b', 3, &ret_b3, &dummy_set },
    Channel{ 'b', 4, &ret_b4, &dummy_set },
    Channel{ 'c', 5, &ret_c5, &dummy_set },
    Channel{ 'c', 1, &ret_c1, &dummy_set }, 
    Channel{ 'd', 2, &ret_d2, &dummy_set }, 
    Channel{ 'd', 3, &ret_d3, &dummy_set }, 
    Channel{ 'e', 4, &ret_e4, &dummy_set },
    Channel{ 'e', 5, &ret_e5, &dummy_set },
  })
);

char serial_in_buffer[128]{0};
unsigned long tot_time = 0;
unsigned long time_a = 0;

mist1::com1::IOHandler<128> io_ctx(
    [](){
      while (Serial.available() == 0)
      { asm volatile("nop"); }
      
      Serial.readBytesUntil('\n', serial_in_buffer, 127);
      time_a = micros();
      
      return serial_in_buffer;
    },

    [](char* str){
#if ENABLE_PRINTF
      printf("%s\n", str);
#else
      Serial.println(str);
#endif
    }
);

mist1::com1::SerialDevice<128, 10> device(io_ctx, lookup);

void setup() {
  Serial.begin(115200);

#if ENABLE_PRINTF
  PRINTF_SERIAL_INIT();
#endif
}

void loop() {
  for (unsigned iter = 0; iter < 1000; ++iter)
  {
    device.communicate();
    tot_time += ( micros() - time_a );
  }
  
  Serial.print("EOF\nCompleted 1000 iterations in: ");
  Serial.print(tot_time);
  Serial.print(" us\n");
  Serial.flush();
  tot_time = 0;
}
