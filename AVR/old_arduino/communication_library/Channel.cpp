#include "Arduino.h"
#include "Channel.h"

mist1::Channel::Channel(String channel_name, 
                        char channel_identifier, 
                        unsigned channel_number, 
                        setFuncPointerDef setFuncPointer,
                        getFuncPointerDef getFuncPointer) : 
                        
	_channel_name(channel_name), 
	_channel_identifier(channel_identifier), 
	_channel_number(channel_number)
{
  _set_func = setFuncPointer;
  _get_func = getFuncPointer;
}

mist1::Channel::Channel() {
  
}

String mist1::Channel::get_name() {
	return _channel_name;
}

char mist1::Channel::get_channel_identifier() {
	return _channel_identifier;
}

unsigned mist1::Channel::get_channel_number() {
	return _channel_number;
}

void mist1::Channel::call_set_func(float value) {
  
  Serial.print("Responding to request to change value of channel ");
  Serial.print(_channel_identifier);
  Serial.print(_channel_number);
  Serial.print(" to ");
  Serial.println(value);
  
  _set_func(value);
}

float mist1::Channel::call_get_func() {
  
  //Serial.print("Responding to request to get value of channel ");
  //Serial.print(_channel_identifier);
  //Serial.println(_channel_number);
  //Serial.println(_get_func());
  return _get_func();
}

