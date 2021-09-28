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
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <EEPROM.h>

#define OLED_RESET 4
Adafruit_SSD1306 display(OLED_RESET);

#define NUMFLAKES 10
#define XPOS 0
#define YPOS 1
#define DELTAY 2

// Relays and Gauge on/off switches
#define RELAY1     50  // unused       
#define RELAY2     51  // Gauge 2 on/off                     
#define RELAY4     52  // Gauge 1 calibrate    
#define RELAY3     53  // Gauge 1 on/off

#define GAUGE1_ON    18
#define GAUGE1_CALIB 3
#define GAUGE2_ON    2

#define GAUGE1_IN    0
#define GAUGE2_IN    1

#if (SSD1306_LCDHEIGHT != 64)
#error("Height incorrect, please fix Adafruit_SSD1306.h!");
#endif

// Define pin for communication LED
#define LED_COM 13

// Global flags for on/off status of ion gauges
boolean gauge1_running = false;
boolean gauge2_running = false;
boolean gauge1_err = false;
boolean gauge2_err = false;

long debouncing_time = 150; //Debouncing Time in Milliseconds
volatile unsigned long last_micros;

volatile bool gauge1_calib_flag = false;

int samples = 100;
double gauge1_raw = 0;
double gauge2_raw = 0;
double gauge1_volt = 0.0;
double gauge2_volt = 0.0;
double gauge1_torr = 0.0;
double gauge2_torr = 0.0;
String gauge1_torr_str = String("0.0e-0");
String gauge2_torr_str = String("0.0e-0");
String gauge1_state = "OFF";
String gauge2_state = "OFF";


// Communication Variables:
char deviceId[37];
char inputMessage[128];

bool LEDStatus = false;

void setup()   { 
  // Initialize the pin for blinking com LED
  pinMode(LED_COM, OUTPUT);
  
  // Initialise the Arduino data pins for OUTPUT
  pinMode(RELAY1, OUTPUT);       
  pinMode(RELAY2, OUTPUT);
  pinMode(RELAY3, OUTPUT);
  pinMode(RELAY4, OUTPUT);
  
  // Initialize the interrupt pins for the pushbutton input
  pinMode(GAUGE1_ON, INPUT);
  pinMode(GAUGE1_CALIB, INPUT);
  pinMode(GAUGE2_ON, INPUT);
  attachInterrupt(digitalPinToInterrupt(GAUGE1_ON), gauge1_on_off_interrupt, RISING);
  attachInterrupt(digitalPinToInterrupt(GAUGE1_CALIB), gauge1_calib_interrupt, RISING);
  attachInterrupt(digitalPinToInterrupt(GAUGE2_ON), gauge2_on_off_interrupt, RISING);

  // Set up external 5V reference
  analogReference(EXTERNAL);

  // Turn all the relays off initially
  digitalWrite(RELAY1,HIGH);          // Turns Relay Off
  digitalWrite(RELAY2,HIGH);          // Turns Relay Off
  digitalWrite(RELAY3,HIGH);          // Turns Relay Off
  digitalWrite(RELAY4,HIGH);          // Turns Relay Off 

  // by default, we'll generate the high voltage from the 3.3v line internally! (neat!)
  display.begin(SSD1306_SWITCHCAPVCC, 0x3C);  // initialize with the I2C addr 0x3C (for the 128x64)
  // init done
  
  // Show image buffer on the display hardware.
  // Since the buffer is intialized with an Adafruit splashscreen
  // internally, this will display the splashscreen.
  // display.display();
  // delay(2000);

  // Clear the buffer.
  display.clearDisplay();

  // text display tests
  display.setTextSize(2);
  display.setTextColor(WHITE);
  display.setCursor(0,0);
  display.print("APG:");
  display.setCursor(54,0);
  display.print("OFF");
  display.setCursor(54,16);
  display.print("0.0e-0");
  display.setCursor(0,32);
  display.print("AIM:");
  display.setCursor(54,32);
  display.print("OFF");
  display.setCursor(54,48);
  display.print("0.0e-0");
  display.display();

  // Get the device ID.
  Serial.begin(115200);

  for (int i=0; i < 36; i++) {
    deviceId[i] = EEPROM.read(i);
  }
  
}

void get_serial_data(char * message) {
  
  int i = 0;
  while(Serial.available()) {
      message[i] = Serial.read();
      i++;
      delay(5);
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

void gauge1_on_off_interrupt()
{

  //Serial.println("Gauge 1 on off interrupt called.");
  
  if((long)(micros() - last_micros) >= debouncing_time * 1000) 
  {
    if (!gauge1_running && !gauge1_err)
    {    
      gauge1_running = true;
      digitalWrite(RELAY4,LOW);   // Turns ON Relay 2
     
      // Change Display
      display.fillRect(54, 0, 74, 16, BLACK);
      display.setCursor(54, 0);
      display.setTextColor(WHITE);
      display.print("ON");
    }
    else
    {
      gauge1_torr_str = String("0.0e-0");
      
      gauge1_running = false;
      gauge1_err = false;
      digitalWrite(RELAY4,HIGH);  // Turns OFF Relay 2
   
      // Change Display
      display.fillRect(54, 0, 74, 16, BLACK);
      display.setCursor(54, 0);
      display.setTextColor(WHITE);
      display.print("OFF");
    }
    last_micros = micros();
  }
}

void gauge1_calib_interrupt()
{
  if((long)(micros() - last_micros) >= debouncing_time * 1000) {
    gauge1_calib_flag = true;    
    last_micros = micros();
  }
}

void gauge2_on_off_interrupt()
{

  //Serial.println("Gauge 2 on off interrupt called.");
  
  if((long)(micros() - last_micros) >= debouncing_time * 1000) 
  {
    if (!gauge2_running && !gauge2_err)
    {    
      gauge2_running = true;
      digitalWrite(RELAY2,LOW);   // Turns ON Relay 2
     
      // Change Display
      display.fillRect(54, 32, 74, 16, BLACK);
      display.setCursor(54,32);
      display.setTextColor(WHITE);
      display.print("ON");
    }
    else
    {
      gauge2_torr_str = String("0.0e-0");
      
      gauge2_running = false;
      gauge2_err = false;
      digitalWrite(RELAY2,HIGH);  // Turns OFF Relay 2
   
      // Change Display
      display.fillRect(54, 32, 74, 16, BLACK);
      display.setCursor(54,32);
      display.setTextColor(WHITE);
      display.print("OFF");
    }
    last_micros = micros();
  }
}

void loop() {

  // Example query message.
  // q01f18 => This means the user wants 01 channels with the names f1 upto a precision of 8.
  
  memset (inputMessage, '\0', 128);

  digitalWrite(RELAY3,HIGH);  // Turns OFF RELAY 3 (gauge 1 calibration)

  // CAVE: Gauge1 is a PIRANI gauge for use in atm down to 10-3 mbar
  if (gauge1_running)
  {    
    analogRead(GAUGE1_IN);
    // Wait for input capacitor to charge
    delay(1);
    gauge1_raw = 0.0;
    for (int i = 0; i < samples; i++)
    {
      gauge1_raw += double(analogRead(GAUGE1_IN));
    }
    gauge1_raw /= double(samples);
    
    gauge1_volt = raw_to_volt(gauge1_raw);
    gauge1_torr = volt_to_torr_pirani(gauge1_volt);
    gauge1_torr_str = formatted_pressure(gauge1_torr);

    //Serial.println(gauge1_volt);

    if (gauge1_volt > 9.2)
    {
      // Above 9.2 means some error state, will probably update this soon 
      // to read out the two known error states at V = 9.5 and V = 9.6
      // We turn it off and set the error state. User can reset the error 
      // state by switching the IG off and then on again.
      gauge1_err = true;
      gauge1_running = false;
      gauge1_torr_str = String("0.0e-0");

      digitalWrite(RELAY1,HIGH);   // Turns OFF Relay 1

      gauge1_state = String("ERR");
    }
    else if (gauge1_volt > 9.1)
    {
      // Above 10 V is considered out of range, so we tell the user and 
      // display the maximum pressure value in the fit (@9.1 V).
      gauge1_state = String("HIGH");
    }
    else if (gauge1_volt < 3.0)
    {
      // Below 3 V is considered out of range, so we tell the user and 
      // display the minimum pressure value in the fit (@3 V).
      gauge1_state = String("LOW");
    }
    else
    {
      // Normal operation
      gauge1_state = String("ON");
    }
    // If the calibration routine has been called through an interrupt, do the 
    // calibration now. Note: Maybe add a short delay here to make sure we are ON > 50 ms?
    if (gauge1_calib_flag){
          digitalWrite(RELAY3,LOW);   // Turns ON  RELAY 3 (gauge 1 calibration)
          gauge1_calib_flag = false;
          delay(50);
    }
  } 
  else 
  {
    if (gauge1_err) gauge1_state = String("ERR");
    else gauge1_state = String("OFF");
    gauge1_torr_str = String("0.0e-0");
    gauge1_calib_flag = false;
  }

  if (gauge2_running)
  {
    analogRead(GAUGE2_IN);
    // Wait for input capacitor to charge
    delay(1);
    gauge2_raw = 0.0;
    for (int i = 0; i < samples; i++)
    {
      gauge2_raw += double(analogRead(GAUGE2_IN));
    }
    gauge2_raw /= double(samples);
    gauge2_volt = raw_to_volt(gauge2_raw);
    gauge2_torr = volt_to_torr(gauge2_volt);
    gauge2_torr_str = formatted_pressure(gauge2_torr);
    
    if (gauge2_volt > 10.7)
    {
      // Above 10.7 means the pressure is high enough to damage the ion gauge.
      // We turn it off and set the error state. User can reset the error 
      // state by switching the IG off and then on again.
      gauge2_err = true;
      gauge2_running = false;
      gauge2_torr_str = String("0.0e-0");

      digitalWrite(RELAY2,HIGH);   // Turns OFF Relay 1
      
      gauge2_state = String("ERR");
    }
    else if (gauge2_volt > 10.0)
    {
      // Above 10 V is considered out of range, so we tell the user and 
      // display the maximum pressure value in the fit (@10 V).
      gauge2_state = String("HIGH");
    }
    else if (gauge2_volt < 2.0)
    {
      // Below 2 V is considered out of range, so we tell the user and 
      // display the minimum pressure value in the fit (@2 V).
      gauge2_state = String("LOW");
    }
    else
    {
      // Normal operation
      gauge2_state = String("ON");
    }
  } 
  else 
  {
    if (gauge2_err) gauge2_state = String("ERR");
    else gauge2_state = String("OFF");
    gauge2_torr_str = String("0.0e-0");
  }
  
  //Serial.println(gauge1_torr_str);
  //Serial.println(gauge2_torr_str);

  //--- Update Display ---//
  // Clear the buffer.
  display.clearDisplay();
  // Text Formatting
  display.setTextSize(2);
  display.setTextColor(WHITE);
  // Do the printing
  display.setCursor(0,0);
  display.print("APG:");
  display.setCursor(54,0);
  display.print(gauge1_state);
  display.setCursor(54,16);
  display.print(gauge1_torr_str);
  display.setCursor(0,32);
  display.print("AIM:");
  display.setCursor(54,32);
  display.print(gauge2_state);
  display.setCursor(54,48);
  display.print(gauge2_torr_str);
  // Show the new display
  display.display();

  // GUI Communication.
  digitalWrite(LED_COM, LOW);
  
  if (Serial.available()) {

    digitalWrite(LED_COM, HIGH);

    get_serial_data(inputMessage);

    char keyword = inputMessage[0];

    if (keyword == 'c') {
      Serial.println("s1,p1");
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
          if (channelIdentifiers[channelIndex] == 's') {
            
            // Gauge state.
            if (channelNumbers[channelIndex] == 0) {
              valueToOutput = (gauge1_state == "OFF") ? 0 : 1;  
            }
            else if (channelNumbers[channelIndex] == 1) {
              valueToOutput = (gauge2_state == "OFF") ? 0 : 1;
            }
          }
          else if (channelIdentifiers[channelIndex] == 'p') {
            // Gauge pressure.
            if (channelNumbers[channelIndex] == 0) {
              valueToOutput = gauge1_torr;
            }
            else if (channelNumbers[channelIndex] == 1) {
              valueToOutput = gauge2_torr;
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
        if (channelNumber == '0') {
          if (valueToSet[0] == '1') {
            if ( ! gauge1_running){
              gauge1_on_off_interrupt();
            }
          } 
          else {
            if (gauge1_running){
              gauge1_on_off_interrupt();
            }
          }
        }
        else if (channelNumber == '1') {
          if (valueToSet[0] == '1') {
            if ( ! gauge2_running){
              gauge2_on_off_interrupt();
            }
          } 
          else {
            if (gauge2_running){
              gauge2_on_off_interrupt();
            }
          }
        }

        if (valueToSet[0] == '1') {
          //Serial.println("Turning the light on!");
          //digitalWrite(LED_COM, HIGH);
        }
        else if (valueToSet[0] == '0') {
          //Serial.println("Turning the light off!");
          //digitalWrite(LED_COM, LOW);
        }

            
      }
      
    }
  }  
}

String formatted_pressure(double pressure)
{
  int exponent;
  double pressure_value;
  String pressure_str;
  if (pressure >= 1.0) {
    
    pressure_str = String(pressure, 1);
    
  } else {
    
    for (int i = 1; i < 12; i++)
    {
      if (int(pressure * pow(10, i)) > 0)
      {
        pressure_value = pressure * pow(10, i);
        exponent = i;
        break;
      }
    }
  
    // Handle case where we have 10e-X
    if (String(pressure_value, 1) == "10.0")
    {
      pressure_value = 1.0;
      exponent -= 1;
    }
    
    pressure_str = String(pressure_value, 1);
    pressure_str.concat("e-");
    pressure_str.concat(exponent);
  }
  
  return pressure_str;
  
}

double raw_to_volt(double raw)
{
  // Arduino samples 5 V into 1024 bins.
  // Because the ion gauges give back 0-10 V, there is a 
  // voltage divider after the differential amplifier.
  return raw / 1023.0 * 5.0 / 3.9 * 8.55 ;
}

double volt_to_torr_pirani(double volt)
{
  if (volt <= 3.0){
    // Below the working pressure regime
    return 1.0e-3;
  }
  if (volt >= 9.1){
    // Above the working pressure regime
    return 944.06;
  }

  return pow(10, (volt - 6.125));
}

double volt_to_torr(double volt)
{
  if (volt <= 2.0){
    // Below the working pressure regime
    return 7.5e-9;
  }
  if (volt >= 10.0){
    // Above the working pressure regime
    return 7.5e-3;
  }
  
  double voltages[38] = {2.0, 2.5, 3.0, 3.2, 3.4, 3.6, 
                         3.8, 4.0, 4.2, 4.4, 4.6, 4.8, 
                         5.0, 5.2, 5.4, 5.6, 5.8, 6.0, 
                         6.2, 6.4, 6.6, 6.8, 7.0, 7.2,
                         7.4, 7.6, 7.8, 8.0, 8.2, 8.4,
                         8.6, 8.8, 9.0, 9.2, 9.4, 9.6, 
                         9.8, 10.0};

  double pressures_mbar[38] = {1.0e-8, 2.4e-8, 5.8e-8, 8.2e-8, 1.2e-7,
                               1.6e-7, 2.3e-7, 3.2e-7, 4.4e-7, 5.9e-7, 
                               7.9e-7, 1.0e-6, 1.3e-6, 1.6e-6, 2.0e-6,
                               2.5e-6, 3.1e-6, 3.9e-6, 4.9e-6, 6.1e-6,
                               7.5e-6, 9.3e-6, 1.1e-5, 1.4e-5, 1.7e-5,
                               2.1e-5, 2.6e-5, 3.1e-5, 3.9e-5, 4.8e-5,
                               6.1e-5, 8.0e-5, 1.1e-4, 1.8e-4, 2.9e-4,
                               5.4e-4, 1.5e-3, 1.0e-2};

  double pressures_torr[38];

  for (int i = 0; i < 38; i++)
  {
    pressures_torr[i] = pressures_mbar[i] * 0.7500616827;
  }

  int index_lower = 0;

  for (int i = 0; i < 37; i++)
  {
    if (volt >= voltages[i] && volt < voltages[i+1])
    {
      // We found the interval, yay.
      index_lower = i;
      break;
    }
  }

  // Do a linear extrapolation to the calibration data
  return pressures_torr[index_lower] + (pressures_torr[index_lower + 1]- pressures_torr[index_lower]) * (volt - voltages[index_lower]) / (voltages[index_lower + 1] - voltages[index_lower]);
}

