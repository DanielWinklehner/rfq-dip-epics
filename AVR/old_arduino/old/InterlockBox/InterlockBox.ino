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

volatile int com_flag = 0;

// Solenoid Valve Variables (Relays). x2.
const int solenoidValvePins[] = {26, 24}; // (relay 1 and 4 are unused on board.)
bool solenoidValveValues[] = {HIGH, HIGH}; // Relays are closed when pulled to ground. Default should be open (HIGH).

// Micro Switches for interlocks. x2.
const int microSwitchPins[] = {2, 3}; 
bool microSwitchValues[] = {LOW, LOW};

// Vacuum Valves. x2.
const int vacuumValvePins[] = {21, 20, 19, 18};
bool vacuumValveMicroSwitchValues[] = {LOW, LOW, LOW, LOW};
bool vacuumValveValues[] = {LOW, LOW};  // For each vacuum valve, two microswitches determine whether or not it's open.

// Communication Variables:
char deviceId[37];
char inputMessage[128];

// Define pins for error state LED, communication LED
#define LED_ERR 12
#define LED_COM 13
#define LED_INTLK_OPEN 11
#define LED_INTLK_CLOSED 10

void setup()   { 
  // Init Com and Error LED's
  pinMode(LED_ERR, OUTPUT);
  pinMode(LED_COM, OUTPUT);
  digitalWrite(LED_COM, LOW);
  digitalWrite(LED_ERR, LOW);
  
  // Initialise the Arduino data pins.

  // Solenoid Valves.
  for (unsigned i = 0; i < sizeof(solenoidValvePins) / sizeof(int); i++) {
    pinMode(solenoidValvePins[i], OUTPUT);
    digitalWrite(solenoidValvePins[i], HIGH);
  }
  
  // Vacuum Valves.
  for (unsigned i = 0; i < sizeof(vacuumValvePins) / sizeof(int); i++) {
    pinMode(vacuumValvePins[i], INPUT);
  }
  
  // Microswitches.
  for (unsigned i = 0; i < sizeof(microSwitchPins) / sizeof(int); i++) {
    pinMode(microSwitchPins[i], INPUT);
  }
    
  Serial.begin(115200);

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
      delay(2);
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
   //
   
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
  
  memset (inputMessage, '\0', 128);
  
  // Read Vacuum Valves.
  for (unsigned i = 0; i < sizeof(vacuumValvePins) / sizeof(int); i++) {
    vacuumValveMicroSwitchValues[i] = digitalRead(vacuumValvePins[i]);
  }

  // Determine whether each of the two vacuum valves are open or not based on the 4 microswitch values.
  // Whether or not a vacuum valve is open depends on the values of two of its associated microswitches.
  for (unsigned i = 0; i < sizeof(vacuumValvePins) / sizeof(int) - 1; i++) {
    if ( (vacuumValveMicroSwitchValues[i]) & ( ! vacuumValveMicroSwitchValues[i + 1] ) ) {
      // Valve is closed.
      vacuumValveValues[((int) (i / 2))] = LOW;
    }
    else if ( ( ! vacuumValveMicroSwitchValues[i]) & (vacuumValveMicroSwitchValues[i + 1] ) ) {
      // Valve is open.
      vacuumValveValues[((int) (i / 2))] = HIGH;
    }
    else {
      // Error State.
    }
  }
  
  // Read Micro Switches.
  for (unsigned i = 0; i < sizeof(microSwitchPins) / sizeof(int); i++) {
    microSwitchValues[i] = digitalRead(microSwitchPins[i]);
  }

  // GUI Communication.
  //digitalWrite(LED_COM, LOW);

  if (Serial.available()) {
    
    //digitalWrite(LED_COM, HIGH);

    get_serial_data(inputMessage);

    char keyword = inputMessage[0];

    if (keyword == 'c') {
      Serial.print("v");
      Serial.print((sizeof(vacuumValveValues) / sizeof(bool)));
      Serial.print(",");
      Serial.print("m");
      Serial.println((sizeof(microSwitchPins) / sizeof(int)));
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
        
        // Apparently, faster than using sprintf.
        if (numberOfChannels > 9) {
          Serial.print(numberOfChannels);
        }
        else {
          Serial.print("0");
          Serial.print(numberOfChannels);
        }
          
        for (int channelIndex = 0; channelIndex < numberOfChannels; channelIndex++) { 
  
          float valueToOutput;        
          if (channelIdentifiers[channelIndex] == 'v') {
            // Vacuum Valve.
            if ((channelNumbers[channelIndex] >= 0) && (channelNumbers[channelIndex] < (sizeof(vacuumValveValues) / sizeof(bool)))) {
              valueToOutput = vacuumValveValues[channelNumbers[channelIndex]];
            } 
          }
          else if (channelIdentifiers[channelIndex] == 'm') {
            // Micro Switch.
            if ((channelNumbers[channelIndex] >= 0) && (channelNumbers[channelIndex] < (sizeof(microSwitchPins) / sizeof(int)))) {
              valueToOutput = microSwitchValues[channelNumbers[channelIndex]];
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

      //float value = atof(valueToSet);

      if (channelIdentifier == 's') {
        
        int number = (channelNumber == '0') ? 0 : 1;

        //if ((valueToSet == '1') && (solenoidValveValues[number] == LOW)) {
        if (valueToSet[0] == '1') {
          solenoidValveValues[number] = HIGH;
          digitalWrite(LED_COM, HIGH);
        }
        //else if ((valueToSet == '0') && (solenoidValveValues[number] == HIGH)) {
        else if (valueToSet[0] == '0') {
          solenoidValveValues[number] = LOW;
          digitalWrite(LED_COM, LOW);
        }
         
      }
    }
  }

  /*
  if (Serial.available()) {
    
    digitalWrite(LED_COM, HIGH);
    
    //  inputCommand = Serial.readString();
    inputCommand = get_serial_data();
    
    int first = inputCommand.indexOf(":");
    int second = inputCommand.indexOf("=");
  
    String keyword = inputCommand.substring(0, first);
    String header = inputCommand.substring(first + 1, second);
    String value = inputCommand.substring(second + 1, inputCommand.length());

    int serialNumberCharacterIndex = header.indexOf("#");
    String serialNumber = header.substring(serialNumberCharacterIndex + 1, header.length());

    String filteredHeader;
    if (serialNumberCharacterIndex > -1) {
      filteredHeader = header.substring(0, serialNumberCharacterIndex);
    }
    else {
      filteredHeader = header;
    }

    if (keyword == "query") {
      if (filteredHeader == "identification") {
        Serial.print("output:device_id=");
        Serial.println(deviceId);
      }
      else if (filteredHeader == "micro_switch") {
        if (serialNumber.toInt() <= (sizeof(microSwitchPins) / sizeof(int))) {
          Serial.print("output:micro_switch#" + serialNumber + "=");
          Serial.println(microSwitchValues[serialNumber.toInt() - 1]);  // We need to subtract 1 because array counting starts from 0 whereas our label counters (micro_switch#1) start from 1.
        }
      }
      else if (filteredHeader == "vacuum_valve") {
        if (serialNumber.toInt() <= sizeof(vacuumValveValues) / sizeof(bool)) {
          Serial.print("output:vacuum_valve#" + serialNumber + "=");
          Serial.println(vacuumValveValues[serialNumber.toInt() - 1]);
        }
      }
    }
    else if (keyword == "set") {
      
      if (filteredHeader == "identified") {
        if (value == "1") {
          deviceIdentified = true;
        }
      }
      else if (filteredHeader == "solenoid_valve") {
        if (value == "1") {
          if (digitalRead(solenoidValvePins[serialNumber.toInt() - 1]) == HIGH) {
            digitalWrite(solenoidValvePins[serialNumber.toInt() - 1], LOW);   
            solenoidValveValues[serialNumber.toInt() - 1] = LOW;   
            Serial.println("assigned:solenoid_valve#" + serialNumber + "=1");
          }
        }
        else if (value == "0") {
          if (digitalRead(solenoidValvePins[serialNumber.toInt() - 1]) == LOW) {
            digitalWrite(solenoidValvePins[serialNumber.toInt() - 1], HIGH);        
            solenoidValveValues[serialNumber.toInt() - 1] = HIGH;   
            Serial.println("assigned:solenoid_valve#" + serialNumber + "=0");   
          }
        }
      }
    }
  }
  */
  
  
}



