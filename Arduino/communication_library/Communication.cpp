#include "Arduino.h"
#include "Communication.h"


mist1::Communication::Communication(String com_name) {
  _com_name = com_name;
}

String mist1::Communication::get_com_name() {
  return _com_name;
}

void mist1::Communication::add_channel(Channel ch) {  
  _all_channels[_number_of_channels] = ch;
  _number_of_channels++;
  /*
  Serial.print("Adding channel ");
  Serial.print(ch.get_name());
  Serial.print(", with identifier ");
  Serial.print(ch.get_channel_identifier());
  Serial.print(", and number ");
  Serial.println(ch.get_channel_number());
  */
}

void mist1::Communication::set_delay_us(int delay_us){
	
	_delay_us = delay_us;
	
}

void mist1::Communication::get_serial_data(char message[128]) {

  memset (message, '\0', 128);

  int i = 0;
  while(Serial.available() > 0) {
      message[i] = Serial.read();
      i++;
      delayMicroseconds(_delay_us);
  }
}


mist1::Channel mist1::Communication::get_channel_by_name(String channel_name) {
  for (unsigned i=0; i < _number_of_channels; i++) {
      if (_all_channels[i].get_name() == channel_name) {
        return _all_channels[i];
      }
  }
}

mist1::Channel mist1::Communication::get_channel_by_identifier_and_number(String channel_identifier, unsigned channel_number) {
  for (unsigned i=0; i < _number_of_channels; i++) {
      if ((_all_channels[i].get_channel_identifier() == channel_identifier[0]) && (_all_channels[i].get_channel_number() == channel_number)) {
        return _all_channels[i];
      }
  }
}

int mist1::Communication::get_number_of_channels_queried(char * inputMessage ) {

  char reportedNumberOfChannels[2] = {inputMessage[1], inputMessage[2]};
  
  // First, find the message length i.e. the length of the message upto the termination character of \0.
  int messageLength = 0;
  char entry = inputMessage[messageLength];
  while (entry != '\0') {
    messageLength++;
    entry = inputMessage[messageLength];
  }
  
  // The query message always begins with a 'q' character. So that's 1 byte. Plus 2 bytes for total number of channels. Then, 3 bytes (2 bytes for name + 1 byte for precision) per channel.
  int numberOfChannels = (messageLength - 3) / 3;

  if (numberOfChannels == atoi(reportedNumberOfChannels)) {
    return numberOfChannels;
  }

  return 0;
  
}

//
// Code From: http://forum.arduino.cc/index.php?topic=46931.0
// davekw7x
// December, 2010
//
// Build a C-style "string" for a floating point variable in a static array.
// The optional "digits" parameter tells how many decimal digits to store
// after the decimal point.  If no "digits" argument is given in the calling
// function a value of 2 is used.
//
// Utility functions to raise 10 to an unsigned int power and to print
// the hex bytes of a floating point variable are also included here.
//
char * mist1::Communication::float2s(float f, unsigned int digits)
{
   
   static char buf[16]; // Buffer to build string representation
   int index = 0;       // Position in buf to copy stuff to

   // For debugging: Uncomment the following line to see what the
   // function is working on.
   //Serial.print("In float2s: bytes of f are: ");printBytes(f);

   // Handle the sign here:
   if (f < 0.0) {
       buf[index++] = '-'; 
       f = -f;
   }
   // From here on, it's magnitude

   // Handle infinities 
   if (isinf(f)) {
       strcpy(buf+index, "INF");
       return buf;
   }
   
   // Handle NaNs
   if (isnan(f)) {
       strcpy(buf+index, "NAN");
       return buf;
   }
   
   //
   // Handle numbers.
   //
   
   // Six or seven significant decimal digits will have no more than
   // six digits after the decimal point.
   //
   // The reason behind limiting ourself to 6 is that, for floats, since they are stored as 32-bit objects, 
   // 8 bits are used for the exponent, 1 bit for the sign and the remaining 23 bits for the maintissa.
   // These remaining 23 bits correspond to 6 to 9 decimal digits, about 7 on average. So, going higher than 6 gives garbage.
   //
   if (digits > 6) {
       //digits = 6;
       static char error[4] = {'E', 'R', 'R', '2'};
       return error;
   }
   else {
     // "Normalize" into integer part and fractional part
     int exponent = 0;
     if (f >= 10) {
         while (f >= 10) {
             f /= 10;
             ++exponent;
         }
     }
     else if ((f > 0) && (f < 1)) {
         while (f < 1) {
             f *= 10;
             --exponent;
         }
     }
  
     //
     // Now add 0.5 in to the least significant digit that will
     // be printed.
  
     //float rounder = 0.5/pow(10, digits);
     // Use special power-of-integer function instead of the
     // floating point library function.
     float rounder = 0.5 / ipow10(digits);
     f += rounder;
  
     //
     // Get the whole number part and the fractional part into integer
     // data variables.
     //
     unsigned intpart = (unsigned)f;
     unsigned long fracpart  = (unsigned long)((f - intpart) * 1.0e7);
  
     //
     // Divide by a power of 10 that zeros out the lower digits
     // so that the "%0.lu" format will give exactly the required number
     // of digits.
     //
     fracpart /= ipow10(6-digits+1);
  
     //
     // Create the format string and use it with sprintf to form
     // the print string.
     //
     char format[16];
     // If digits > 0, print
     //    int part decimal point fraction part and exponent.
  
     if (digits) {
       
         sprintf(format, "%%u.%%0%dlu E%%+d", digits);
         //
         // To make sure the format is what it is supposed to be, uncomment
         // the following line.
         //Serial.print("format: ");Serial.println(format);
         sprintf(buf+index, format, intpart, fracpart, exponent);
     }
     else { // digits == 0; just print the intpart and the exponent
         sprintf(format, "%%u E%%+d");
         sprintf(buf+index, format, intpart, exponent);
     }
  
     return buf;
   }
   
} 

// Raise 10 to an unsigned integer power,
// It's used in this program for powers
// up to 6, so it must have a long return
// type, since in avr-gcc, an int can't hold
// 10 to the power 6.
//
// Since it's an integer function, negative
// powers wouldn't make much sense.
//
// If you want a more general function for raising
// an integer to an integer power, you could make 
// "base" a parameter.
unsigned long mist1::Communication::ipow10(unsigned power)
{
   const unsigned base = 10;
   unsigned long retval = 1;

   for (int i = 0; i < power; i++) {
       retval *= base;
   }
   return retval;
}

void mist1::Communication::convert_scientific_notation_to_mist1(char * source, char * target, unsigned precision) {
  

  // Serial.println(source);

  // First figure out the sign.
  int index = 0;
  
  if (source[0] == '-') {
    target[0] = '-';
    index++;          // For negative numbers, there's a '-' character in the front so we need to offset by 1.
  }
  else {
    target[0] = '+';
  }
  
  // Next, we want the first digit.
  target[1] = source[index];

  // The next character is a decimal point. We don't want that.
  

  if (precision == 0) {

    // If precision is 0, we want to go to int (instead of float) i.e. we do not want any digits after the decimal. 
    
    // Next, we want the exponent. Assumes that the exponent is always going to be single-digit.
    // There's a space, an 'E' and then the sign of the exponent before the actual exponent.
  
    target[2 + precision] = source[index + 2 + 0 + 2];

    // Finally, the sign of the exponent.
    target[2 + precision + 1] = source[index + 2 + 0 + 1];
  }
  else {

    // Next, we want the digits after the decimal.

    for (unsigned i = 0; i < precision; i++) {
      target[2 + i] = source[index + 2 + i];
    }
  
    // Next, we want the exponent. Assumes that the exponent is always going to be single-digit.
    // There's a space, an 'E' and then the sign of the exponent before the actual exponent.
  
    target[2 + precision] = source[index + 2 + precision + 3];

    // Finally, the sign of the exponent.
    target[2 + precision + 1] = source[index + 2 + precision + 2];
  }
 
}


void mist1::Communication::respond_to_input_message() {
  char inputMessage[128];
  get_serial_data(inputMessage);

  
  char keyword = inputMessage[0];

  if (keyword == 'c') {
    
    Serial.println(get_all_channel_names());
    
  } else if (keyword == 'i') {

    Serial.println(get_all_channel_identifiers());
    
  } else if (keyword == 'n') {

    Serial.println(_com_name);
    
  } else if (keyword == 'q') {
    // Query.

    // Find what the user is querying for.
    int numberOfChannels = get_number_of_channels_queried(inputMessage);


    // Read input message.
    unsigned precisions[numberOfChannels];
    char channelIdentifiers[numberOfChannels];
    unsigned channelNumbers[numberOfChannels];

    // Check if the number of channels queried for are small enough to fit in a single message of length 128.
    // For each channel, we need (1 + 1) + (1 + 1 + precision + 1 + 1) [ { channel_name(1) + channel_number(1) } + { sign(1) + number(1) + precision + exponent(1) + exponent sign(1) } ].
    // Need to add 3 to that. [ 'o'(1) + number_of_channels(2) ].
    unsigned totalMessageLength = 3;

    // Move this to just calculating the length of the string built because right now we're wasting some time because for almost all inputs, the length is NOT going to be > 128.
    
    for (unsigned channelIndex = 0; channelIndex < numberOfChannels; channelIndex++) {
      channelIdentifiers[channelIndex] = inputMessage[3 + 3*channelIndex];  // Need to add 3 because the first three characters are going to be the keyword (1) + total number of channels (2).
      channelNumbers[channelIndex] = inputMessage[3 + 3*channelIndex + 1] - '0'; // "- '0'" to convert from char to int.
      precisions[channelIndex] =  inputMessage[3 + 3*channelIndex + 2] - '0';  // "- '0'" to convert from char to int.

      totalMessageLength += (1 + 1) + (1 + 1 + precisions[channelIndex] + 1 + 1);
    }

    String messageToReturn = "o";

    bool precisionError = false;
    bool channelNotFoundError = false;
    
    for (unsigned channelIndex = 0; channelIndex < numberOfChannels; channelIndex++) {
      
      bool channelFound = false;
      
      for (unsigned i=0; i < _number_of_channels; i++) {

        //Serial.print("Querying channel: ");
        //Serial.print(channelIdentifiers[channelIndex]);
        //Serial.println(channelNumbers[channelIndex]);
        
        if ((char)_all_channels[i].get_channel_identifier() == channelIdentifiers[channelIndex]){
          if (_all_channels[i].get_channel_number() == channelNumbers[channelIndex]){
            
            channelFound = true;
            
            float valueToOutput = _all_channels[i].call_get_func();
            
            char * buff = float2s(valueToOutput, precisions[channelIndex]);

            char precisionErrorString[4] = {'E', 'R', 'R', '2'};

            // Terrible way to do this.
            if ((buff[0] == precisionErrorString[0]) && (buff[1] == precisionErrorString[1]) && (buff[2] == precisionErrorString[2]) && (buff[3] == precisionErrorString[3])) {
              // User asked for a precision > 6 for one of the channels.
              precisionError = true;
              break;
            }
            
            char valueToPrint[1 + 1 + precisions[channelIndex] + 1 + 1 + 1]; // sign(1) + digit(1) + precision + exponent(1) + sign(1) + termination character(1).
            memset(valueToPrint, '\0', (1 + 1 + precisions[channelIndex] + 1 + 1 + 1));
            convert_scientific_notation_to_mist1(buff, valueToPrint, precisions[channelIndex]);

            
            String new_addition = (String) channelIdentifiers[channelIndex] + (String) channelNumbers[channelIndex] + valueToPrint;
            messageToReturn += new_addition;
            
            break;
          }     
        }
      }

      if ( ! channelFound) {
        channelNotFoundError = true;
        break;
      }
      else if (precisionError) {
        break;
      }
      else {
        // Last channel. Add a carriage return.
        if (channelIndex == (numberOfChannels - 1)) { 
          messageToReturn += "\r\n";
        }
      }
    }
    
    
    if (numberOfChannels < 1) {
      Serial.println("ERR3");
    }
    else if (channelNotFoundError) {
      Serial.println("ERR4");
    }
    else if (precisionError) {
      Serial.println("ERR1");
    }
    else if (messageToReturn.length() > 128) {
      Serial.println("ERR2");
    }
    else {
      Serial.print(messageToReturn);
    }
      
  } else if (keyword == 's') {
    
    // Setting values.
    char channelIdentifier = inputMessage[1];
    String channelNumber = (String) inputMessage[2];

    for (unsigned i=0; i < _number_of_channels; i++) {
      
      if ((char)_all_channels[i].get_channel_identifier() == channelIdentifier){
        
        if ((String)_all_channels[i].get_channel_number() == channelNumber){

          float valueToSetNumerical = get_value_to_set(inputMessage);

          _all_channels[i].call_set_func(valueToSetNumerical);
        }
      }
    }
  }
}


float mist1::Communication::get_value_to_set(char * inputMessage){
  // Find out the length of the value.
  int index = 3;
  char currentChar = inputMessage[index];
  while (currentChar != '\0') {
    index++;
    currentChar = inputMessage[index];
  }

  // Get numerical value to set
  int valueLength = index - 3;
  char valueToSet[valueLength];
  for (unsigned i = 0; i < valueLength; i++) {
    valueToSet[i] = inputMessage[3 + i];
  }

  //float valueToSetNumerical;
  //sscanf(valueToSet, "%f", &valueToSetNumerical);

  float valueToSetNumerical = atof(valueToSet);

  return valueToSetNumerical;
}


String mist1::Communication::get_all_channel_names() {
  String all_channel_names = "";

  for (unsigned i=0; i < _number_of_channels; i++) {
    all_channel_names += _all_channels[i].get_name();
    all_channel_names += (i == (_number_of_channels - 1)) ? "" : ";";
  }

  return all_channel_names;
  
}

String mist1::Communication::get_all_channel_identifiers() {
  String all_channel_ids = "";
  String id, no;

  for (unsigned i=0; i < _number_of_channels; i++) {
    
    id = (String)_all_channels[i].get_channel_identifier();
    no = (String)_all_channels[i].get_channel_number();
    all_channel_ids += id + no;
    all_channel_ids += (i == (_number_of_channels - 1)) ? "" : ";";
  }

  return all_channel_ids;
}

