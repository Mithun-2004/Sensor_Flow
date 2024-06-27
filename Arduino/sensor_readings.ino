const int temperatureSensorPin = A1;

const int pressureSensorPin = A0;

void setup() {
  // Initialize serial communication at 9600 baud rate
  Serial.begin(9600);
}

void loop() {

  int tempSensorValue = analogRead(temperatureSensorPin);


  float temperature = map(tempSensorValue, 0, 1023, -10, 40);


  int pressureSensorValue = analogRead(pressureSensorPin);


  float pressure = map(pressureSensorValue, 0, 1023, 0, 100); 
  Serial.print("Temperature: ");
  Serial.print(temperature);
  Serial.println(" °C");

  Serial.print("Pressure: ");
  Serial.print(pressure);
  Serial.println(" kPa");

 
  delay(1000);


}
