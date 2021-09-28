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
#define RELAY1     50                        
#define RELAY2     51                       
#define RELAY3     52                       
#define RELAY4     53
#define HIGH1      31
#define HIGH2      33
#define HIGH3      35
#define LOW1       30
#define LOW2       32
#define LOW3       34
#define GAUGE1_ON  2
#define GAUGE2_ON  3
#define GAUGE1_IN  0
#define GAUGE2_IN  1

#define LOGO16_GLCD_HEIGHT 16 
#define LOGO16_GLCD_WIDTH  16 
static const unsigned char PROGMEM logo16_glcd_bmp[] =
{ B00000000, B11000000,
  B00000001, B11000000,
  B00000001, B11000000,
  B00000011, B11100000,
  B11110011, B11100000,
  B11111110, B11111000,
  B01111110, B11111111,
  B00110011, B10011111,
  B00011111, B11111100,
  B00001101, B01110000,
  B00011011, B10100000,
  B00111111, B11100000,
  B00111111, B11110000,
  B01111100, B11110000,
  B01110000, B01110000,
  B00000000, B00110000 };

#if (SSD1306_LCDHEIGHT != 64)
#error("Height incorrect, please fix Adafruit_SSD1306.h!");
#endif

// Global flags for on/off status of ion gauges
boolean gauge1_running = false;
boolean gauge2_running = false;
boolean gauge1_err = false;
boolean gauge2_err = false;

int samples = 200;
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

void setup()   { 
  // Initialise the Arduino data pins for OUTPUT
  pinMode(RELAY1, OUTPUT);       
  pinMode(RELAY2, OUTPUT);
  pinMode(RELAY3, OUTPUT);
  pinMode(RELAY4, OUTPUT);
  pinMode(GAUGE1_ON, INPUT);
  pinMode(GAUGE2_ON, INPUT);

  pinMode(HIGH1, OUTPUT); 
  pinMode(HIGH2, OUTPUT);
  pinMode(HIGH3, OUTPUT);

  pinMode(LOW1, OUTPUT); 
  pinMode(LOW2, OUTPUT);
  pinMode(LOW3, OUTPUT);

  digitalWrite(HIGH1,HIGH);
  digitalWrite(HIGH2,HIGH);
  digitalWrite(HIGH3,HIGH);

  digitalWrite(LOW1,LOW);
  digitalWrite(LOW2,LOW);
  digitalWrite(LOW3,LOW);

  digitalWrite(RELAY1,HIGH);          // Turns Relay Off
  digitalWrite(RELAY2,HIGH);          // Turns Relay Off
  digitalWrite(RELAY3,HIGH);          // Turns Relay Off
  digitalWrite(RELAY4,HIGH);          // Turns Relay Off 

  attachInterrupt(digitalPinToInterrupt(GAUGE1_ON), gauge1_interrupt, CHANGE);
  attachInterrupt(digitalPinToInterrupt(GAUGE2_ON), gauge2_interrupt, CHANGE);
                 
//  Serial.begin(9600);

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
}

void loop() {
  //delay(50);

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
      // display the maximum pressure value in the fit (@10 V).
      gauge1_state = String("HIGH");
    }
    else if (gauge1_volt < 3.0)
    {
      // Below 3 V is considered out of range, so we tell the user and 
      // display the minimum pressure value in the fit (@2 V).
      gauge1_state = String("LOW");
    }
    else
    {
      // Normal operation
      gauge1_state = String("ON");
    }
  } 
  else 
  {
    if (gauge1_err) gauge1_state = String("ERR");
    else gauge1_state = String("OFF");
    gauge1_torr_str = String("0.0e-0");
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
  // Arduino samples 5 V into 1024 bins. Breakout board has a voltage divider with
  // R2 = 4.96 kOhm and R1 + R2 = 14.89 kOhm
  return raw / 1024.0 * 5.0 / 4.96 * 14.89;
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

void gauge1_interrupt()
{
//  Serial.println("Interrupt1\n");
  if (digitalRead(GAUGE1_ON) == HIGH && !gauge1_running && !gauge1_err)
  {
    //Serial.println("Switching Gauge1 on\n");
    gauge1_running = true;
    
    //digitalWrite(RELAY1,LOW);   // Turns ON Relay 1

    gauge1_state = String("ON");

  }
  if (digitalRead(GAUGE1_ON) == LOW)
  {
    //Serial.println("Switching Gauge1 off\n");
    
    gauge1_running = false;
    gauge1_err = false;

    digitalWrite(RELAY1,HIGH);   // Turns OFF Relay 1
    
    gauge1_state = String("OFF");
    gauge1_torr_str = String("0.0e-0");
    
  }
}

void gauge2_interrupt()
{
//  Serial.println("Interrupt2\n");
  if (digitalRead(GAUGE2_ON) == HIGH && !gauge2_running && !gauge1_err)
  {
//    Serial.println("Switching Gauge2 on\n");
    
    gauge2_running = true;
    
    digitalWrite(RELAY2,LOW);   // Turns ON Relay 2
   
    // Change Display
    display.fillRect(54, 32, 74, 16, BLACK);
    display.setCursor(54,32);
    display.setTextColor(WHITE);
    display.print("ON");
  }
  if (digitalRead(GAUGE2_ON) == LOW)
  {
//    Serial.println("Switching Gauge2 off\n");

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
}

void testfillrect(void) {
  uint8_t color = 1;
  for (int16_t i=0; i<display.height()/2; i+=3) {
    // alternate colors
    display.fillRect(i, i, display.width()-i*2, display.height()-i*2, color%2);
    display.display();
    color++;
  }
}

void testdrawchar(void) {
  display.setTextSize(1);
  display.setTextColor(WHITE);
  display.setCursor(0,0);

  for (uint8_t i=0; i < 168; i++) {
    if (i == '\n') continue;
    display.write(i);
    if ((i > 0) && (i % 21 == 0))
      display.println();
  }    
  display.display();
}

void testdrawline() {  
  for (int16_t i=0; i<display.width(); i+=4) {
    display.drawLine(0, 0, i, display.height()-1, WHITE);
    display.display();
  }
  for (int16_t i=0; i<display.height(); i+=4) {
    display.drawLine(0, 0, display.width()-1, i, WHITE);
    display.display();
  }
  delay(250);
  
  display.clearDisplay();
  for (int16_t i=0; i<display.width(); i+=4) {
    display.drawLine(0, display.height()-1, i, 0, WHITE);
    display.display();
  }
  for (int16_t i=display.height()-1; i>=0; i-=4) {
    display.drawLine(0, display.height()-1, display.width()-1, i, WHITE);
    display.display();
  }
  delay(250);
  
  display.clearDisplay();
  for (int16_t i=display.width()-1; i>=0; i-=4) {
    display.drawLine(display.width()-1, display.height()-1, i, 0, WHITE);
    display.display();
  }
  for (int16_t i=display.height()-1; i>=0; i-=4) {
    display.drawLine(display.width()-1, display.height()-1, 0, i, WHITE);
    display.display();
  }
  delay(250);

  display.clearDisplay();
  for (int16_t i=0; i<display.height(); i+=4) {
    display.drawLine(display.width()-1, 0, 0, i, WHITE);
    display.display();
  }
  for (int16_t i=0; i<display.width(); i+=4) {
    display.drawLine(display.width()-1, 0, i, display.height()-1, WHITE); 
    display.display();
  }
  delay(250);
}

void testscrolltext(void) {
  display.setTextSize(2);
  display.setTextColor(WHITE);
  display.setCursor(10,0);
  display.clearDisplay();
  display.println("scroll");
  display.display();
 
  display.startscrollright(0x00, 0x0F);
  delay(2000);
  display.stopscroll();
  delay(1000);
  display.startscrollleft(0x00, 0x0F);
  delay(2000);
  display.stopscroll();
  delay(1000);    
  display.startscrolldiagright(0x00, 0x07);
  delay(2000);
  display.startscrolldiagleft(0x00, 0x07);
  delay(2000);
  display.stopscroll();
}
