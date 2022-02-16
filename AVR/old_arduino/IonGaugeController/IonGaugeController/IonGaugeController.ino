#include <Channel.h>
#include <Communication.h>

// Set up serial communication
char inputMessage[128];
mist1::Communication com = mist1::Communication("Ion Gauge Controller");
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

#define OLED_RESET 4
Adafruit_SSD1306 display(OLED_RESET);

#define NUMFLAKES 10
#define XPOS 0
#define YPOS 1
#define DELTAY 2

// Relays and Gauge on/off switches
#define RELAY1     50  // unused       
#define RELAY2     51  // Gauge 2 on/off                     
#define RELAY4     52  // Gauge 1 on/off    
#define RELAY3     53  // Gauge 1 calibration

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

long debouncing_time = 150000;  // Debouncing Time (us)
volatile unsigned long last_micros;

long display_sleep_time = 100000;  // Time between updates of the display (us)
volatile unsigned int display_last_micros;

volatile bool gauge1_calib_flag = false;

int samples = 50;
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

bool LEDStatus = false;

float get_apg_pressure(){
  return gauge1_torr;
}

float get_aim_pressure(){
  return gauge2_torr;
}

void dummyFunc(float set_value){
  //Serial.println("Called the dummy function!");
}

void setup()   { 
  Serial.begin(115200);
  
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
  
  com.add_channel(mist1::Channel("APG_PRESSURE", 'p', 1, &dummyFunc, &get_apg_pressure));
  com.add_channel(mist1::Channel("AIM_PRESSURE", 'p', 2, &dummyFunc, &get_aim_pressure));

}

void gauge1_on_off_interrupt()
{

  //Serial.println("Gauge 1 on off interrupt called.");
  
  if((long)(micros() - last_micros) >= debouncing_time) 
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
  if((long)(micros() - last_micros) >= debouncing_time) {
    gauge1_calib_flag = true;    
    last_micros = micros();
  }
}

void gauge2_on_off_interrupt()
{

  //Serial.println("Gauge 2 on off interrupt called.");
  
  if((long)(micros() - last_micros) >= debouncing_time) 
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

      digitalWrite(RELAY4,HIGH);   // Turns OFF Relay 1

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
    if (gauge1_err) {
      gauge1_state = String("ERR");
      if (gauge1_calib_flag){
          digitalWrite(RELAY3,LOW);   // Turns ON  RELAY 3 (gauge 1 calibration)
          gauge1_calib_flag = false;
          delay(50);
          gauge1_state = String("RST");
      }
    }
    else {
      gauge1_state = String("OFF");
    }
    gauge1_torr_str = String("0.0e-0");
    //gauge1_calib_flag = false;
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

  //--- Update Display only every few milliseconds ---//
  if ((long)(micros() - display_last_micros) >= display_sleep_time)
  {
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
    display_last_micros = micros();
  }
  // GUI Communication.
  digitalWrite(LED_COM, LOW);

  if (Serial.available()) {
    
    digitalWrite(LED_COM, HIGH);
    
    com.respond_to_input_message();

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

