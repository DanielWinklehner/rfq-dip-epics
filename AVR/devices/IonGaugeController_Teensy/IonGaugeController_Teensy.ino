//#include <Channel.h>
//#include <Communication.h>
#include <libcom1.hpp>

// Compile with Teensy 3.6?

#define USE_OLED
//#define DEBUG

// Set up serial communication
//char inputMessage[128];
//mist1::Communication com = mist1::Communication("IGC2");

#ifdef USE_OLED
 #include <SPI.h>
 #include <Wire.h>
 #include <Adafruit_GFX.h>
 #include <Adafruit_SSD1306.h>
 #define OLED_RESET 4
 Adafruit_SSD1306 display(OLED_RESET);
 #if (SSD1306_LCDHEIGHT != 64)
   #error("Height incorrect, please fix Adafruit_SSD1306.h!");
 #endif
 long display_sleepy_time = 500000;
 volatile unsigned int display_last_micros = 0;
#endif

// Relays and Gauge on/off switches
#define RELAY1     31  // unused       
#define RELAY2     32  // Gauge 2 on/off                     
#define RELAY4     29  // Gauge 1 calibrate    
#define RELAY3     30  // Gauge 1 on/off

#define GAUGE1_ON    9
#define GAUGE1_OFF   8
#define GAUGE1_CALIB 10
#define GAUGE2_ON    7
#define GAUGE2_OFF   6

#define GAUGE1_IN    A2
#define GAUGE2_IN    A20

// Define pin for communication LED
#define LED_COM 12
#define LED_ERR 11

// Some ADC stuff
int samples = 150;
int res = 12;
float gauge1_calib = 10.0 / 0.86;  // Diff Amp input stage has A=0.1
float gauge1_factor = 1.02525 * gauge1_calib / pow(2.0, (float) res) / (float) samples;
float gauge2_calib = 10.0 / 0.86;  // Diff Amp input stage has A=0.1
float gauge2_factor = 1.02525 * gauge2_calib / pow(2.0, (float) res) / (float) samples;

// Global flags for on/off status of ion gauges
boolean gauge1_running = false;
boolean gauge2_running = false;
boolean gauge1_err = false;
boolean gauge2_err = false;

long debouncing_time = 150; //Debouncing Time in Milliseconds
volatile unsigned long last_micros;

volatile bool gauge1_calib_flag = false;

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
String gauge1_volt_str = "";
String gauge2_volt_str = "";

bool LEDStatus = false;

float get_apg_pressure(){
  return gauge1_torr;
}

float get_aim_pressure(){
  return gauge2_torr;
}

void dummySetFunc(float set_value){
  //Serial.println("Called the dummy function!");
}


using mist1::com1::Channel;
MakeChannelMap(lookup, 2, ({
    Channel{ 'p', 1, &get_apg_pressure, &dummySetFunc},
    Channel{ 'p', 2, &get_aim_pressure, &dummySetFunc},
  })
);

char serial_in_buffer[128]{0};
// Template parameter is buffer size for the output buffer
mist1::com1::IOHandler<128> io_ctx(
    // Read from the serial port
    [](){
      while (Serial.available() == 0)                       //
      { asm volatile("nop"); }                              //
      Serial.readBytesUntil('\n', serial_in_buffer, 127);   //
      return serial_in_buffer;
    },
    // Write to the serial port
    [](char* str){
      Serial.println(str);
    }
);

mist1::com1::SerialDevice<128, 2> device(io_ctx, lookup);

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
  pinMode(GAUGE1_ON, INPUT_PULLUP);
  pinMode(GAUGE1_OFF, INPUT_PULLUP);
  pinMode(GAUGE1_CALIB, INPUT);
  pinMode(GAUGE2_ON, INPUT_PULLUP);
  pinMode(GAUGE2_OFF, INPUT_PULLUP);
  
  attachInterrupt(digitalPinToInterrupt(GAUGE1_ON), gauge1_on_interrupt, FALLING);
  attachInterrupt(digitalPinToInterrupt(GAUGE1_OFF), gauge1_off_interrupt, FALLING);
  attachInterrupt(digitalPinToInterrupt(GAUGE1_CALIB), gauge1_calib_interrupt, FALLING);
  attachInterrupt(digitalPinToInterrupt(GAUGE2_ON), gauge2_on_interrupt, FALLING);
  attachInterrupt(digitalPinToInterrupt(GAUGE2_OFF), gauge2_off_interrupt, FALLING);
  
  // Set up internal 1.2 V reference
  analogReference(INTERNAL);
  analogReadResolution(res);

  // Turn all the relays off initially
  digitalWrite(RELAY1,HIGH);          // Turns Relay Off
  digitalWrite(RELAY2,HIGH);          // Turns Relay Off
  digitalWrite(RELAY3,HIGH);          // Turns Relay Off
  digitalWrite(RELAY4,HIGH);          // Turns Relay Off 

#ifdef USE_OLED
  display.begin(SSD1306_SWITCHCAPVCC, 0x3C);  // initialize with the I2C addr 0x3C (for the 128x64)
  
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
#endif
  /*
  com.add_channel(mist1::Channel("APG_PRESSURE", 'p', 1, &dummyFunc, &get_apg_pressure));
  com.add_channel(mist1::Channel("AIM_PRESSURE", 'p', 2, &dummyFunc, &get_aim_pressure));
  */
}

void gauge1_on_interrupt()
{

  //Serial.println("Gauge 1 on off interrupt called.");
  
  if((long)(micros() - last_micros) >= debouncing_time * 1000) 
  {
    if (!gauge1_running && !gauge1_err)
    {    
      gauge1_running = true;
      digitalWrite(RELAY4,LOW);   // Turns ON Relay 2
#ifdef USE_OLED
      // Change Display
      display.fillRect(54, 0, 74, 16, BLACK);
      display.setCursor(54, 0);
      display.setTextColor(WHITE);
      display.print("ON");
#endif
    }
  last_micros = micros();
  }
}

void gauge1_off_interrupt()
{

  //Serial.println("Gauge 1 on off interrupt called.");
  
  if((long)(micros() - last_micros) >= debouncing_time * 1000) 
  {

      gauge1_torr_str = String("0.0e-0");
      
      gauge1_running = false;
      gauge1_err = false;
      digitalWrite(RELAY4,HIGH);  // Turns OFF Relay 2
      
#ifdef USE_OLED
      // Change Display
      display.fillRect(54, 0, 74, 16, BLACK);
      display.setCursor(54, 0);
      display.setTextColor(WHITE);
      display.print("OFF");
#endif

    last_micros = micros();
  }
}

void gauge1_calib_interrupt()
{
  //Serial.println("Gauge 1 calib interrupt called.");
  if((long)(micros() - last_micros) >= debouncing_time * 1000) {
    gauge1_calib_flag = true;    
    last_micros = micros();
  }
}

void gauge2_on_interrupt()
{

  //Serial.println("Gauge 2 on off interrupt called.");
  
  if((long)(micros() - last_micros) >= debouncing_time * 1000) 
  {
    if (!gauge2_running && !gauge2_err)
    {    
      gauge2_running = true;
      digitalWrite(RELAY2,LOW);   // Turns ON Relay 2

#ifdef USE_OLED
      // Change Display
      display.fillRect(54, 32, 74, 16, BLACK);
      display.setCursor(54,32);
      display.setTextColor(WHITE);
      display.print("ON");
#endif
    }
    last_micros = micros();
  }
}

void gauge2_off_interrupt()
{

  //Serial.println("Gauge 2 on off interrupt called.");
  
  if((long)(micros() - last_micros) >= debouncing_time * 1000) 
  {
      gauge2_torr_str = String("0.0e-0");
      
      gauge2_running = false;
      gauge2_err = false;
      digitalWrite(RELAY2,HIGH);  // Turns OFF Relay 2
#ifdef USE_OLED
      // Change Display
      display.fillRect(54, 32, 74, 16, BLACK);
      display.setCursor(54,32);
      display.setTextColor(WHITE);
      display.print("OFF");
#endif
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
    
    gauge1_volt = gauge1_raw * gauge1_factor;
    gauge1_volt_str = String(gauge1_volt, 1);
    gauge1_torr = volt_to_torr_pirani(gauge1_volt);
    gauge1_torr_str = formatted_pressure(gauge1_torr);

    if (gauge1_volt > 9.2)
    {
      // Above 9.2 means some error state, will probably update this soon 
      // to read out the two known error states at V = 9.5 and V = 9.6
      // We turn it off and set the error state. User can reset the error 
      // state by switching the IG off and then on again.
      gauge1_err = true;
      //gauge1_running = false;
      //gauge1_torr_str = String("0.0e-0");

      //digitalWrite(RELAY4,HIGH);   // Turns OFF Relay 1

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
          delay(60);
          digitalWrite(RELAY3,HIGH);   // Turns ON  RELAY 3 (gauge 1 calibration)
    }
  } 
  else 
  {
    if (gauge1_err) {
      gauge1_state = String("ERR");
      if (gauge1_calib_flag){
        digitalWrite(RELAY4,LOW);   // Turns ON Relay 4 temporarily so gauge has power
        delay(50);
        digitalWrite(RELAY3,LOW);   // Turns ON  RELAY 3 (gauge 1 calibration)
        delay(60);
        digitalWrite(RELAY3,HIGH);   // Turns ON  RELAY 3 (gauge 1 calibration)
        digitalWrite(RELAY4,HIGH);   // Turns OFF Relay 4
        gauge1_calib_flag = false;
      }
    }
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
    //gauge2_raw = gauge2_raw * factor / double(samples);
    //gauge2_volt = raw_to_volt(gauge2_raw);

    gauge2_volt = gauge2_raw * gauge2_factor;  
    gauge2_volt_str = String(gauge2_volt, 1);
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

#ifdef USE_OLED

  if ((long) (micros() - display_last_micros) >= display_sleepy_time) {
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
#ifdef DEBUG
    display.setCursor(0,16);
    display.print(gauge1_volt_str);
#endif
    display.setCursor(54,16);
    display.print(gauge1_torr_str);
    //display.print(gauge1_volt);
    display.setCursor(0,32);
    display.print("AIM:");
    display.setCursor(54,32);
    display.print(gauge2_state);
#ifdef DEBUG
    display.setCursor(0,32);
    display.print(gauge2_volt_str);
#endif
    display.setCursor(54,48);
    display.print(gauge2_torr_str);
    //display.print(gauge2_volt);
    // Show the new display
    display.display();
    display_last_micros = micros();
  }
#endif

#ifdef DEBUG
  Serial.print("APG: ");
  Serial.print(gauge1_volt);
  Serial.print(" V, ");
  Serial.print("AIM: ");
  Serial.print(gauge2_volt);
  Serial.println(" V");
#endif

  // GUI Communication.
  digitalWrite(LED_COM, LOW);

  if (Serial.available()) {
    
    digitalWrite(LED_COM, HIGH);
    
    //com.respond_to_input_message();
    device.communicate();
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
