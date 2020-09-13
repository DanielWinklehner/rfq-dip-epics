#ifndef Communication_h
#define Communication_h

#include "Arduino.h"
#include "Channel.h"


using namespace std;

namespace mist1 {
  class Communication {
    
    public:
      Communication(String com_name);
      String get_com_name();
  
      void add_channel(Channel ch);
  
      //get_action();
        
      void get_serial_data(char message[128]);
      int get_number_of_channels_queried(char * inputMessage );
      float get_value_to_set(char * inputMessage );
      char * float2s(float f, unsigned int digits=2);
      unsigned long ipow10(unsigned power);
      void convert_scientific_notation_to_mist1(char * source, char * target, unsigned precision);

      String get_all_channel_names();
      String get_all_channel_identifiers();

      Channel get_channel_by_name(String channel_name);
      Channel get_channel_by_identifier_and_number(String identifier, unsigned number);
      
      void respond_to_input_message();
      void set_delay_us(int delay_us);
     
    private:
      String _com_name;
      Channel _all_channels[16];
      int _number_of_channels = 0;
	  int _delay_us = 50;
      
  };  
}


#endif
