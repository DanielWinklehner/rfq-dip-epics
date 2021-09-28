//#define Interrupt1 2
//#define Interrupt2 3
//#define Interrupt3 18
//#define Interrupt4 19
//#define Interrupt5 20
//#define Interrupt6 21

#define LED 13

//#define PWM1 8 // Pin 8 is controlled by prescaler 4 (timer4)
//#define PWM2 9 // Pin 9 is controlled by prescaler 2 (timer2)

//volatile boolean led_on = false;
//volatile int frequency1 = 0;
//int freq_write1 = 0;
//volatile int frequency2 = 0;
//int freq_write2 = 0;
//volatile int frequency3 = 0;
//int freq_write3 = 0;
//volatile int frequency4 = 0;
//int freq_write4 = 0;
//volatile int frequency5 = 0;
//int freq_write5 = 0;
//volatile int frequency6 = 0;
//int freq_write6 = 0;
//unsigned long currentTime;
//unsigned long cloopTime;

void setup() {
  //First clear all three prescaler bits:
//  int myEraser = 7;             // this is 111 in binary and is used as an eraser
//  TCCR2B &= ~myEraser;   // this operation (AND plus NOT),  set the three bits in TCCR2B to 0
//
//  int myPrescaler = 1;         // this could be a number in [1 , 6]. 3 corresponds in binary to 011.   
//  TCCR2B |= myPrescaler;  //this operation (OR), replaces the last three bits in TCCR2B with our new value 011
  
  // Set up serial communication
//  Serial.begin(9600);
  // Set digital pin modes (input/output)
  pinMode(LED, OUTPUT);
//  pinMode(Interrupt1, INPUT);
//  pinMode(Interrupt2, INPUT);
//  pinMode(Interrupt3, INPUT);
//  pinMode(Interrupt4, INPUT);
//  pinMode(Interrupt5, INPUT);
//  pinMode(Interrupt6, INPUT);

//  pinMode(PWM1, OUTPUT);
//  analogWrite(PWM1, 127);
//  pinMode(PWM2, OUTPUT);
//  analogWrite(PWM2, 127);
//
//  // Attach the interrupts for flow meters
//  attachInterrupt(digitalPinToInterrupt(Interrupt1), test_interrupt1, RISING);
//  attachInterrupt(digitalPinToInterrupt(Interrupt2), test_interrupt2, RISING);
//  attachInterrupt(digitalPinToInterrupt(Interrupt3), test_interrupt3, RISING);
//  attachInterrupt(digitalPinToInterrupt(Interrupt4), test_interrupt4, RISING);
//  attachInterrupt(digitalPinToInterrupt(Interrupt5), test_interrupt5, FALLING);
//  attachInterrupt(digitalPinToInterrupt(Interrupt6), test_interrupt6, FALLING);

  // Set initial states for digital pins
  digitalWrite(LED, HIGH);
}

//void test_interrupt1() {
//  frequency1++;
//}
//
//void test_interrupt2() {
//  frequency2++;
//}
//
//void test_interrupt3() {
//  frequency3++;
//}
//
//void test_interrupt4() {
//  frequency4++;
//}
//
//void test_interrupt5() {
//  frequency5++;
//}
//
//void test_interrupt6() {
//  frequency6++;
//}

void loop() {
  // put your main code here, to run repeatedly:
//  currentTime = millis();
//  // Every second, calculate and print litres/hour
//  if(currentTime >= (cloopTime + 1000))
//  {
//    cloopTime = currentTime; // Updates cloopTime
//    freq_write1 = frequency1; //
//    freq_write2 = frequency2; //
//    freq_write3 = frequency3; //
//    freq_write4 = frequency4; //
//    freq_write5 = frequency5; //
//    freq_write6 = frequency6; //
//    frequency1 = 0; // Reset Counter
//    frequency2 = 0; // Reset Counter
//    frequency3 = 0; // Reset Counter
//    frequency4 = 0; // Reset Counter
//    frequency5 = 0; // Reset Counter
//    frequency6 = 0; // Reset Counter
//    Serial.print("f1 = ");
//    Serial.print(freq_write1, DEC); // Print litres/hour
//    Serial.print(" Hz, ");
//    Serial.print("f2 = ");
//    Serial.print(freq_write2, DEC); // Print litres/hour
//    Serial.print(" Hz, ");
//    Serial.print("f3 = ");
//    Serial.print(freq_write3, DEC); // Print litres/hour
//    Serial.print(" Hz, ");
//    Serial.print("f4 = ");
//    Serial.print(freq_write4, DEC); // Print litres/hour
//    Serial.print(" Hz, ");
//    Serial.print("f5 = ");
//    Serial.print(freq_write5, DEC); // Print litres/hour
//    Serial.print(" Hz, ");
//    Serial.print("f6 = ");
//    Serial.print(freq_write6, DEC); // Print litres/hour
//    Serial.println(" Hz");
//  }
//  if (led_on){
    digitalWrite(LED, HIGH);
    delay(500);
    digitalWrite(LED, LOW);
//  }
//  led_on = !led_on;
}
