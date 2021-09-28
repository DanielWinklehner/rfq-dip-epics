/*********************************************************************
This is an example for our Monochrome OLEDs based on SSD1306 drivers

  Pick one up today in the adafruit shop!
  ------> http://www.adafruit.com/category/63_98

This example is for a 128x64 size display using I2C to communicate
3 pins are required to interface (2 I2C and one reset)

Adafruit invests time and resources providing this open source code, 
please support Adafruit and open-source hardware by purchasing 
products from Adafruit!

Written by Limor Fried/Ladyada  for Adafruit Industries.  
BSD license, check license.txt for more information
All text above, and the splash screen must be included in any redistribution
*********************************************************************/

#include <SPI.h>
#include <Wire.h>
#include <EEPROM.h>

// Define pins for error state LED, communication LED
#define LED_ERR 39
#define LED_COM 13

#define p1 12
#define p2 10

#define a1 0
#define a2 3

// Communication Variables:
char deviceId[37];
char inputMessage[128];

void setup()   { 
  // Init Com and Error LED's
  pinMode(LED_ERR, OUTPUT);
  pinMode(LED_COM, OUTPUT);
  digitalWrite(LED_COM, LOW);
  digitalWrite(LED_ERR, LOW);

  Serial.begin(115200); // 115200

  // Get this Arduino's device ID from memory.
  for (int i=0; i < 36; i++) {
    deviceId[i] = EEPROM.read(i);
  }  
}

void get_serial_data(char * message) {
  
  int i = 0;
  while(Serial.available()) {
      message[i] = Serial.read();
      i++;
      delay(1);
  }
}

int get_number_of_channels_queried(char * inputMessage ) {

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
char *float2s(float f, unsigned int digits=2)
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
   // Six or seven significant decimal digits will have no more than
   // six digits after the decimal point.
   //
   if (digits > 6) {
       digits = 6;
   }
   
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


//
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
unsigned long ipow10(unsigned power)
{
   const unsigned base = 10;
   unsigned long retval = 1;

   for (int i = 0; i < power; i++) {
       retval *= base;
   }
   return retval;
}

void convert_scientific_notation_to_mist1(char * source, char * target, unsigned precision) {
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

void loop() {

  // Example query message.
  // q01f18 => This means the user wants 01 channels with the names f1 upto a precision of 8.
  // sp1512 => THis means the user wants to set the channel p1 to 512.
  
  memset (inputMessage, '\0', 128);
  //Serial.print("Did a main loop");
   
  // GUI Communication.
  digitalWrite(LED_COM, LOW);
  
  if (Serial.available()) {
    
    digitalWrite(LED_COM, HIGH);

    get_serial_data(inputMessage);

    // Serial.println(inputMessage);

    char keyword = inputMessage[0];

    if (keyword == 'c') {
      ;
    }
    else if (keyword == 'q') {
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
      
      for (unsigned channelIndex = 0; channelIndex < numberOfChannels; channelIndex++) {
        channelIdentifiers[channelIndex] = inputMessage[3 + 3*channelIndex];  // Need to add 3 because the first three characters are going to be the keyword (1) + total number of channels (2).
        channelNumbers[channelIndex] = inputMessage[3 + 3*channelIndex + 1] - '0'; // "- '0'" to convert from char to int.
        precisions[channelIndex] =  inputMessage[3 + 3*channelIndex + 2] - '0';  // "- '0'" to convert from char to int.

        totalMessageLength += (1 + 1) + (1 + 1 + precisions[channelIndex] + 1 + 1);
      }

      if (totalMessageLength > 128) {
        Serial.println("error");
      }
      else {
        if (numberOfChannels > 0) {
          Serial.print("o");
        }
        
        // Apparently faster than using sprintf.
        if (numberOfChannels > 9) {
          Serial.print(numberOfChannels);
        }
        else {
          Serial.print("0");
          Serial.print(numberOfChannels);
        }
          
        for (int channelIndex = 0; channelIndex < numberOfChannels; channelIndex++) { 
  
          float valueToOutput;    
          // All the quering for values goes here...    
          if (channelIdentifiers[channelIndex] == 'a') {
            // read 'a' for analog in 
            if (channelNumbers[channelIndex] == 0){
              //valueToOutput = random(0, 10);
              valueToOutput = 432.123;
            }
          }
  
          char * buff = float2s(valueToOutput, precisions[channelIndex]);
          char valueToPrint[1 + 1 + precisions[channelIndex] + 1 + 1 + 1]; // sign(1) + digit(1) + precision + exponent(1) + sign(1) + termination character(1).
          memset(valueToPrint, '\0', (1 + 1 + precisions[channelIndex] + 1 + 1 + 1));
          convert_scientific_notation_to_mist1(buff, valueToPrint, precisions[channelIndex]);

          Serial.print(channelIdentifiers[channelIndex]);
          Serial.print(channelNumbers[channelIndex]);
          Serial.print(valueToPrint);
          
          // Last channel. Add a carriage return.
          if (channelIndex == (numberOfChannels - 1)) {
            Serial.print("\r\n");
          }
        }
      } 
    }
    else if (keyword == 's') {
      // Setting values.

      char channelIdentifier = inputMessage[1];
      char channelNumber = inputMessage[2];

      // Find out the length of the value.
      int index = 3;
      char currentChar = inputMessage[index];
      while (currentChar != '\0') {
        index++;
        currentChar = inputMessage[index];
      }

      int valueLength = index - 3;
      
      char valueToSet[valueLength];
      for (unsigned i = 0; i < valueLength; i++) {
        valueToSet[i] = inputMessage[3 + i];
      }

      if (channelIdentifier == 'd') {
        if (channelNumber == '1'){
        // 'p' for pwm, channel '0'
        // value should be in 'valueToSet' need to transform into int or float!
        // Stuff you want to do with the value goes here...
        
        int valueToSetNumerical;
        sscanf(valueToSet, "%d", &valueToSetNumerical);
        Serial.println("Setting device1: "+(String)valueToSetNumerical + " ("+(String)(valueToSetNumerical*5./1023.)+"V)");
        analogWrite(p1, valueToSetNumerical);
        }     
      if (channelNumber == '2'){
        int valueToSetNumerical;
        sscanf(valueToSet, "%d", &valueToSetNumerical);
        Serial.println("Setting device2: "+(String)valueToSetNumerical + " ("+(String)(valueToSetNumerical*5./1023.)+"V)");
        analogWrite(p2, valueToSetNumerical);
       }
      }
     }
    else if (keyword == 'r') {
      char channelIdentifier = inputMessage[1];
      char channelNumber = inputMessage[2];
      if (channelIdentifier == 'd') {
        if (channelNumber == '1') {
          Serial.println("Reading device1: " + (String)analogRead(a1) );
        }
        else if (channelNumber == '2') {
          Serial.println("Reading device2: " + (String)analogRead(a2) );
        }
      }
    }
 


  }
  else {
  // Serial.println("Serial not available!");
  }
}


