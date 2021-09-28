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
#include <MAX31856.h>

// Flow meters. x5.
const int flowSensorPins[] = {18, 19, 20, 3, 2};
volatile int flowSensorFreqs[] = {0, 0, 0, 0, 0};
float flowSensorFreqsWrite[] = {0.0, 0.0, 0.0, 0.0, 0.0};
unsigned long currentTime;
unsigned long cloopTime;

// Temperature Sensors. 8x.
// The power requirement for the board is less than 2mA.  Most microcontrollers can source or sink a lot more
// than that one each I/O pin.  For example, the ATmega328 supports up to 20mA.  So it is possible to power the
// board using I/O pins for power - so you can turn the board on and off (if you want to).
// FAULT and DRDY are not used by the library (see above)
#define SCK1    44
#define SDI1    42
#define SDO1    40

#define SCK2    49
#define SDI2    51
#define SDO2    53

#define CS1    46
#define CS2    48
#define CS3    50
#define CS4    52
#define CS5    47
#define CS6    45
#define CS7    43
#define CS8    41

// Define pins for error state LED, communication LED
#define LED_ERR 12
#define LED_COM 13

// MAX31856 Initial settings (see MAX31856.h and the MAX31856 datasheet)
// The default noise filter is 60Hz, suitable for the USA
#define CR0_INIT  (CR0_AUTOMATIC_CONVERSION + CR0_OPEN_CIRCUIT_FAULT_TYPE_K /* + CR0_NOISE_FILTER_50HZ */)
#define CR1_INIT  (CR1_AVERAGE_2_SAMPLES + CR1_THERMOCOUPLE_TYPE_K)
#define MASK_INIT (~(MASK_VOLTAGE_UNDER_OVER_FAULT + MASK_THERMOCOUPLE_OPEN_FAULT))

MAX31856 *temperature1;
MAX31856 *temperature2;
MAX31856 *temperature3;
MAX31856 *temperature4;
MAX31856 *temperature5;
MAX31856 *temperature6;
MAX31856 *temperature7;
//MAX31856 *temperature8;

// Communication Variables:
char deviceId[37];
char inputMessage[128];

float t[] = {0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0};

void setup()   { 
  // Init Com and Error LED's
  pinMode(LED_ERR, OUTPUT);
  pinMode(LED_COM, OUTPUT);
  digitalWrite(LED_COM, LOW);
  digitalWrite(LED_ERR, LOW);
  
  // Flow Meters.
  for (unsigned i = 0; i < sizeof(flowSensorPins) / sizeof(int); i++) {
    pinMode(flowSensorPins[i], INPUT);
    // Activate the pullup resistor
    digitalWrite(flowSensorPins[i], HIGH);
  }

  Serial.begin(115200); // 115200

  // Get this Arduino's device ID from memory.
  for (int i=0; i < 36; i++) {
    deviceId[i] = EEPROM.read(i);
  }

  // Interrupts for flow sensors.
  attachInterrupt(digitalPinToInterrupt(flowSensorPins[0]), flow_interrupt0, RISING);
  attachInterrupt(digitalPinToInterrupt(flowSensorPins[1]), flow_interrupt1, RISING);
  attachInterrupt(digitalPinToInterrupt(flowSensorPins[2]), flow_interrupt2, RISING);
  attachInterrupt(digitalPinToInterrupt(flowSensorPins[3]), flow_interrupt3, RISING);
  attachInterrupt(digitalPinToInterrupt(flowSensorPins[4]), flow_interrupt4, RISING);

  // Define the pins used to communicate with the MAX31856
  temperature1 = new MAX31856(SDI1, SDO1, CS1, SCK1);
  temperature2 = new MAX31856(SDI1, SDO1, CS2, SCK1);
  temperature3 = new MAX31856(SDI1, SDO1, CS3, SCK1);
  temperature4 = new MAX31856(SDI1, SDO1, CS4, SCK1);
  temperature5 = new MAX31856(SDI2, SDO2, CS5, SCK2);
  temperature6 = new MAX31856(SDI2, SDO2, CS6, SCK2);
  temperature7 = new MAX31856(SDI2, SDO2, CS7, SCK2);
//  temperature8 = new MAX31856(SDI2, SDO2, CS8, SCK2);
  
  // Initializing the MAX31855's registers
  temperature1->writeRegister(REGISTER_CR0, CR0_INIT);
  temperature1->writeRegister(REGISTER_CR1, CR1_INIT);
  temperature1->writeRegister(REGISTER_MASK, MASK_INIT);

  temperature2->writeRegister(REGISTER_CR0, CR0_INIT);
  temperature2->writeRegister(REGISTER_CR1, CR1_INIT);
  temperature2->writeRegister(REGISTER_MASK, MASK_INIT);

  temperature3->writeRegister(REGISTER_CR0, CR0_INIT);
  temperature3->writeRegister(REGISTER_CR1, CR1_INIT);
  temperature3->writeRegister(REGISTER_MASK, MASK_INIT);

  temperature4->writeRegister(REGISTER_CR0, CR0_INIT);
  temperature4->writeRegister(REGISTER_CR1, CR1_INIT);
  temperature4->writeRegister(REGISTER_MASK, MASK_INIT);

  temperature5->writeRegister(REGISTER_CR0, CR0_INIT);
  temperature5->writeRegister(REGISTER_CR1, CR1_INIT);
  temperature5->writeRegister(REGISTER_MASK, MASK_INIT);

  temperature6->writeRegister(REGISTER_CR0, CR0_INIT);
  temperature6->writeRegister(REGISTER_CR1, CR1_INIT);
  temperature6->writeRegister(REGISTER_MASK, MASK_INIT);

  temperature7->writeRegister(REGISTER_CR0, CR0_INIT);
  temperature7->writeRegister(REGISTER_CR1, CR1_INIT);
  temperature7->writeRegister(REGISTER_MASK, MASK_INIT);

//  temperature8->writeRegister(REGISTER_CR0, CR0_INIT);
//  temperature8->writeRegister(REGISTER_CR1, CR1_INIT);
//  temperature8->writeRegister(REGISTER_MASK, MASK_INIT);
  
}

void flow_interrupt0() {
  flowSensorFreqs[0]++;
}

void flow_interrupt1() {
  flowSensorFreqs[1]++;
}

void flow_interrupt2() {
  flowSensorFreqs[2]++;
}

void flow_interrupt3() {
  flowSensorFreqs[3]++;
}

void flow_interrupt4() {
  flowSensorFreqs[4]++;
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
  //Serial.print("Did a main loop");

  // Get the current time in milliseconds
  currentTime = millis();
  
  // Every half second, calculate and print litres/hour, and read temperatures
  // The temperatures can be moved into their own if clause to read them 
  // out more often.
  if(currentTime >= (cloopTime + 500)) {
    
    cloopTime = currentTime; // Updates cloopTime
    // Read Flow Meters.
    
    for (unsigned i = 0; i < sizeof(flowSensorPins) / sizeof(int); i++) {
      flowSensorFreqsWrite[i] = (float)flowSensorFreqs[i] * 0.06; //(1000 pulses per l, 60 s in a min, measuring for 0.5 s)
      flowSensorFreqs[i] = 0; // Reset counter.
    }
    
    // Temperature sensors (read out every half second for now)
    t[0] = temperature1->readThermocouple(CELSIUS);
    t[1] = temperature2->readThermocouple(CELSIUS);
    t[2] = temperature3->readThermocouple(CELSIUS);
    t[3] = temperature4->readThermocouple(CELSIUS);
    t[4] = temperature5->readThermocouple(CELSIUS);
    t[5] = temperature6->readThermocouple(CELSIUS);
    t[6] = temperature7->readThermocouple(CELSIUS);
    // t[7] = temperature8->readThermocouple(CELSIUS);
  }
   
  // GUI Communication.
  digitalWrite(LED_COM, LOW);
  
  if (Serial.available()) {
    
    digitalWrite(LED_COM, HIGH);

    get_serial_data(inputMessage);

    // Serial.println(inputMessage);

    char keyword = inputMessage[0];

    if (keyword == 'c') {
      Serial.print("f");
      Serial.print((sizeof(flowSensorPins) / sizeof(int)));
      Serial.print(",");
      Serial.print("t");
      Serial.println((sizeof(t) / sizeof(float)));
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
          if (channelIdentifiers[channelIndex] == 'f') {
            // Flow meter.
            if ((channelNumbers[channelIndex] >= 0) && (channelNumbers[channelIndex] < (sizeof(flowSensorPins) / sizeof(int)))) {
              //valueToOutput = flowSensorFreqsWrite[channelNumbers[channelIndex]];
              //valueToOutput = random(0, 10);
              valueToOutput = 1.2345;
            } 
          }
          else if (channelIdentifiers[channelIndex] == 't') {
            // Temperature sensor.
            if ((channelNumbers[channelIndex] >= 0) && (channelNumbers[channelIndex] < (sizeof(t) / sizeof(float)))) {
              //valueToOutput = t[channelNumbers[channelIndex]];
              valueToOutput = random(10, 20);
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

    /*
    // Get the message from the serial port
    inputCommand = get_serial_data();

    // Dissect the message into it's components
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

    
    Serial.print("keyword: ");
    Serial.print(keyword);
    Serial.print(", header: ");
    Serial.print(filteredHeader);
    Serial.print(", number: ");
    Serial.print(serialNumber);
    Serial.print(", response: ");
   
    
    // Do stuff with the message components according to the GUI commands
    if (keyword == "query") {
      if (filteredHeader == "identification") {
        Serial.print("output:device_id=");
        Serial.println(deviceId);
      }
      else if (filteredHeader == "flow_meter") {
        if (serialNumber.toInt() <= (sizeof(flowSensorPins) / sizeof(int))) {
          Serial.print("output:flow_meter#"  + serialNumber + "=");  
          Serial.println(flowSensorFreqsWrite[serialNumber.toInt() - 1], 2);
        } 
      }
      else if (filteredHeader == "temp_sensor") {
        if (serialNumber.toInt() <= (sizeof(t) / sizeof(float))) {
          Serial.print("output:temp_sensor#"  + serialNumber + "=");
          Serial.println(t[serialNumber.toInt() - 1], 2);
        } 
      }
    }
    else if (keyword == "set") {
      if (filteredHeader == "identified") {
        if (value == "1") {
          deviceIdentified = true;
        }
      }
    }

  */
  
  }
  else {
   //Serial.println("Serial not available!");
  }
}


