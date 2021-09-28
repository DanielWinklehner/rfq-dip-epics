#include <Channel.h>
#include <Communication.h>
#include <MAX31856.h>

// Set up serial communication
char inputMessage[128];
mist1::Communication com = mist1::Communication("TemperatureSensor");

#define LED_COM 13
#define LED_ERR 2  // unused at the moment

// Temperature Sensors. 4x.
// The power requirement for the board is less than 2mA.  Most microcontrollers can source or sink a lot more
// than that one each I/O pin.  For example, the ATmega328 supports up to 20mA.  So it is possible to power the
// board using I/O pins for power - so you can turn the board on and off (if you want to).
// FAULT and DRDY are not used by the library (see above)
#define SCK 8
#define SDI 9
#define SDO 7
#define CS1 6
#define CS2 5
#define CS3 4
#define CS4 3

// MAX31856 Initial settings (see MAX31856.h and the MAX31856 datasheet)
// The default noise filter is 60Hz, suitable for the USA
#define CR0_INIT  (CR0_AUTOMATIC_CONVERSION + CR0_OPEN_CIRCUIT_FAULT_TYPE_K /* + CR0_NOISE_FILTER_50HZ */)
#define CR1_INIT  (CR1_AVERAGE_2_SAMPLES + CR1_THERMOCOUPLE_TYPE_K)
#define MASK_INIT (~(MASK_VOLTAGE_UNDER_OVER_FAULT + MASK_THERMOCOUPLE_OPEN_FAULT))

MAX31856 *temperature1;
MAX31856 *temperature2;
MAX31856 *temperature3;
MAX31856 *temperature4;

float get_t1(){
  return temperature1->readThermocouple(CELSIUS);
}

float get_t2(){
  return temperature2->readThermocouple(CELSIUS);
}

float get_t3(){
  return temperature3->readThermocouple(CELSIUS);
}

float get_t4(){
  return temperature4->readThermocouple(CELSIUS);
}

// Print the temperature, or the type of fault
void printTemperature(double temperature) {
  switch ((int) temperature) {
    case FAULT_OPEN:
      Serial.print("FAULT_OPEN");
      break;
    case FAULT_VOLTAGE:
      Serial.print("FAULT_VOLTAGE");
      break;
    case NO_MAX31856:
      Serial.print("NO_MAX31856");
      break;
    default:
      Serial.print(temperature);
      break;
  }
  Serial.print(" ");
}

float get_t1_fault(){
    // query fault code;
    // Display the junction (IC) temperature first
    // Sometimes the junction temperature is not provided until a thermocouple is attached
    double temperature = temperature1->readJunction(CELSIUS);
    Serial.print("J");
    Serial.print("=");
    printTemperature(temperature);

    // Display the thermocouple temperature
    temperature = temperature1->readThermocouple(CELSIUS);
    Serial.print("T");
    Serial.print("=");
    printTemperature(temperature);

    Serial.println();
}

float get_t2_fault(){
    // query fault code;
    // Display the junction (IC) temperature first
    // Sometimes the junction temperature is not provided until a thermocouple is attached
    double temperature = temperature2->readJunction(CELSIUS);
    Serial.print("J");
    Serial.print("=");
    printTemperature(temperature);

    // Display the thermocouple temperature
    temperature = temperature2->readThermocouple(CELSIUS);
    Serial.print("T");
    Serial.print("=");
    printTemperature(temperature);

    Serial.println();
}

float get_t3_fault(){
    // query fault code;
    // Display the junction (IC) temperature first
    // Sometimes the junction temperature is not provided until a thermocouple is attached
    double temperature = temperature3->readJunction(CELSIUS);
    Serial.print("J");
    Serial.print("=");
    printTemperature(temperature);

    // Display the thermocouple temperature
    temperature = temperature3->readThermocouple(CELSIUS);
    Serial.print("T");
    Serial.print("=");
    printTemperature(temperature);

    Serial.println();
}

float get_t4_fault(){
    // query fault code;
    // Display the junction (IC) temperature first
    // Sometimes the junction temperature is not provided until a thermocouple is attached
    double temperature = temperature4->readJunction(CELSIUS);
    Serial.print("J");
    Serial.print("=");
    printTemperature(temperature);

    // Display the thermocouple temperature
    temperature = temperature4->readThermocouple(CELSIUS);
    Serial.print("T");
    Serial.print("=");
    printTemperature(temperature);

    Serial.println();
}

void dummySetFunc(float set_value){
  //Serial.println("Called the dummy function!");
}

float dummyGetFunc(){
  //Serial.println("Called the dummy function!");
}

void setup() {
  
  Serial.begin(115200);

  pinMode(LED_COM, OUTPUT);
  pinMode(LED_ERR, OUTPUT);
  
  digitalWrite(LED_ERR, HIGH);
  
  // Define the pins used to communicate with the MAX31856
  temperature1 = new MAX31856(SDI, SDO, CS1, SCK);
  temperature2 = new MAX31856(SDI, SDO, CS2, SCK);
  temperature3 = new MAX31856(SDI, SDO, CS3, SCK);
  temperature4 = new MAX31856(SDI, SDO, CS4, SCK);
  
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

  com.add_channel(mist1::Channel("TEMP1", 't', 1, &dummySetFunc, &get_t1));
  com.add_channel(mist1::Channel("TEMP2", 't', 2, &dummySetFunc, &get_t2));
  com.add_channel(mist1::Channel("TEMP3", 't', 3, &dummySetFunc, &get_t3));
  com.add_channel(mist1::Channel("TEMP4", 't', 4, &dummySetFunc, &get_t4));

  com.add_channel(mist1::Channel("FAULT1", 'f', 1, &dummySetFunc, &get_t1_fault));
  com.add_channel(mist1::Channel("FAULT2", 'f', 2, &dummySetFunc, &get_t2_fault));
  com.add_channel(mist1::Channel("FAULT3", 'f', 3, &dummySetFunc, &get_t3_fault));
  com.add_channel(mist1::Channel("FAULT4", 'f', 4, &dummySetFunc, &get_t4_fault));

  digitalWrite(LED_ERR, LOW);
}

void loop() {
  // put your main code here, to run repeatedly:

  // GUI Communication.
  digitalWrite(LED_COM, LOW);
  
  if (Serial.available()) {
    digitalWrite(LED_COM, HIGH);
    com.respond_to_input_message();
  }  
}
