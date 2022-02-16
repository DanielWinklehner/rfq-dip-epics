#ifndef Channel_h
#define Channel_h

#include "Arduino.h"

// Typedefs for the function pointer of the set/get functions
typedef void (*setFuncPointerDef) (float);
typedef float  (*getFuncPointerDef) ();

using namespace std;

namespace mist1 {
  class Channel {
  	
  	public:
  		Channel(String channel_name, char channel_identifier, unsigned channel_number, 
  		        setFuncPointerDef setFuncPointer, getFuncPointerDef getFuncPointer);
              
  		Channel();
      
  		String get_name();
  		char get_channel_identifier();
  		unsigned get_channel_number();
        void call_set_func(float value);
        float call_get_func();
  
  	private:
  		String _channel_name;
  		char _channel_identifier;
  		unsigned _channel_number;
      setFuncPointerDef _set_func;
      getFuncPointerDef _get_func;
  };
};

#endif
