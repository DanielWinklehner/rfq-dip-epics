#include <libcom1.hpp>
#include <MAX31856.h>

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

using mist1::com1::Channel;
char serial_in_buffer[128]{0};

void dummy_set(float){}

// Obtain temp. and junction
float get_t1() { return temperature1->readThermocouple(CELSIUS); }
float get_t2() { return temperature2->readThermocouple(CELSIUS); }
float get_t3() { return temperature3->readThermocouple(CELSIUS); }
float get_t4() { return temperature4->readThermocouple(CELSIUS); }

float get_j1() { return temperature1->readJunction(CELSIUS); }
float get_j2() { return temperature2->readJunction(CELSIUS); }
float get_j3() { return temperature3->readJunction(CELSIUS); }
float get_j4() { return temperature4->readJunction(CELSIUS); }

// Faults for temperature and junctions
float get_f1() { return check_fault( get_t1() ); }
float get_f2() { return check_fault( get_t2() ); }
float get_f3() { return check_fault( get_t3() ); }
float get_f4() { return check_fault( get_t4() ); }

float get_a1() { return check_fault( get_j1() ); }
float get_a2() { return check_fault( get_j2() ); }
float get_a3() { return check_fault( get_j3() ); }
float get_a4() { return check_fault( get_j4() ); }

// check_fault determines if there is an issue with the thermocouple
// each reading gets a fault, and each fault is a PV
float check_fault(double temperature) {
  switch ((int) temperature) {
    case FAULT_OPEN:
      return 3.0f;
      break;
    
    case FAULT_VOLTAGE:
      return 2.0f;
      break;
    
    case NO_MAX31856:
      return 1.0f;
      break;
    
    default:
      return 0.0f;
      break;
  }
}


MakeChannelMap(lookup, 16, ({
    Channel{ 't', 1, &get_t1, &dummy_set },
    Channel{ 't', 2, &get_t2, &dummy_set },
    Channel{ 't', 3, &get_t3, &dummy_set },
    Channel{ 't', 4, &get_t4, &dummy_set },
    Channel{ 'j', 1, &get_j1, &dummy_set },
    Channel{ 'j', 2, &get_j2, &dummy_set },
    Channel{ 'j', 3, &get_j3, &dummy_set },
    Channel{ 'j', 4, &get_j4, &dummy_set },
    Channel{ 'f', 1, &get_f1, &dummy_set },
    Channel{ 'f', 2, &get_f2, &dummy_set },
    Channel{ 'f', 3, &get_f3, &dummy_set },
    Channel{ 'f', 4, &get_f4, &dummy_set },
    Channel{ 'a', 1, &get_a1, &dummy_set },
    Channel{ 'a', 2, &get_a2, &dummy_set },
    Channel{ 'a', 3, &get_a3, &dummy_set },
    Channel{ 'a', 4, &get_a4, &dummy_set }
  })
);

mist1::com1::IOHandler<512> io_ctx(
  //Read
  [](){
    while (Serial.available() == 0) { asm volatile("nop"); }
    digitalWrite(LED_COM, HIGH);
    Serial.readBytesUntil('\n', serial_in_buffer, 128);
    digitalWrite(LED_COM, LOW);
    return serial_in_buffer;
  },

  //Write
  [](char* str){
    digitalWrite(LED_COM, HIGH);
    Serial.println(str);
    digitalWrite(LED_COM, LOW);
  }
);

mist1::com1::SerialDevice<512, 16> device(io_ctx, lookup);

void setup() {
  Serial.begin(19200);

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
  
  digitalWrite(LED_ERR, LOW);
}

void loop() {
  device.communicate();
}

