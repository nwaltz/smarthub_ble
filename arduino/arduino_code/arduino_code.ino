#include <ArduinoBLE.h>
#include "Arduino_BMI270_BMM150.h"
// #include "ble/Gap.h"
// #include <Arduino_LSM9DS1.h>
//#include <Arduino_HTS221.h>       // Pressure Sensor Library
//#include <Arduino_LPS22HB.h>      // Temperature Sensor Library

//----------------------------------------------------------------------------------------------------------------------
// BLE
//----------------------------------------------------------------------------------------------------------------------

#define LED_PIN 24 //22 for red(right) 24 for green (left)

#define UNIT_ID "9999"
#define UNIT_SIDE "Right"

//Create variable to send data through BLE
byte message_bytes[18];

// BLE Service Name
BLEService customService("0000290c-0000-1000-8000-00805f9b34fb");

// BLE Characteristics
// Syntax: BLE<DATATYPE>Characteristic <NAME>(<UUID>, <PROPERTIES>, <DATA LENGTH>)
BLECharacteristic ble_data("2A56", BLERead | BLENotify, sizeof message_bytes);
BLEDescriptor dataDescriptor("beca6057-955c-4f8a-e1e3-56a1633f04b1", "Smarthub Data");

const int BLE_MODE_PIN = LED_BUILTIN;
//const int RSSI_LED_PIN = LED_PWR;

union unionForm1 { //Union to store state in bytes
  byte unionByte;
  unsigned int unionInt;
} stateUnion;

union unionForm2 { //Union to store message data in bytes
  byte unionBytes[2];
  unsigned int unionInt;
} messageUnion;

bool accel_flipper = true;

void setup()
{
  //inmitialize LED pin
  pinMode(LED_PIN, OUTPUT);
  // Initalizing all the sensors
  IMU.begin();
  Serial.begin(9600);
  delay(2000);
  // while (!Serial);
  if (!BLE.begin())
  {
    Serial.println("BLE failed to Initiate");
    delay(500);
    while (1);
  }

  // Setting BLE Name
  String deviceName = String(UNIT_SIDE) + " Smarthub: " + String(UNIT_ID);
  BLE.setDeviceName(deviceName.c_str());
  BLE.setLocalName(deviceName.c_str());

  // BLE.setConnectionInterval(0x0010, 0x0020); // 20ms to 40ms
  // BLE.setConnectionLatency(0);

  // Setting BLE Service Advertisment
  BLE.setAdvertisedService(customService);

  //Add descriptor to charcteristic
  ble_data.addDescriptor(dataDescriptor);

  // Adding characteristics to BLE Service Advertisment
  customService.addCharacteristic(ble_data);

  // Adding the service to the BLE stack
  BLE.addService(customService);

  // Start advertising
  BLE.stopAdvertise();
  delay(3000);
  BLE.advertise();
  Serial.println("Bluetooth device is now active, waiting for connections...");
} // setup


void loop()
{
  digitalWrite(LED_PIN, HIGH);
  static unsigned long previousMillis = 0;
  static unsigned long previousReadMillis = 0;
  // listen for BLE peripherals to connect:
  BLEDevice central = BLE.central();
  if ( central )
  {
    float message_interval = (1.0 / 17) * 1000;
    float sensor_interval = message_interval / 4.0;

    while ( central.connected() )
    {
      
      if ( millis() - previousMillis >= message_interval )
      {
        previousMillis = millis();
        float gyroX, gyroY, gyroZ;
        float accelX, accelY, accelZ;
        float accel_z_vec[4] = {0, 0, 0, 0};
        float gyro_y_vec[4] = {0, 0, 0, 0};

        int i = 0;
        while (i < 4) {
          if (millis() - previousReadMillis >= sensor_interval)
          {
            if ( IMU.gyroscopeAvailable() )
            {
              previousReadMillis = millis();

              IMU.readGyroscope( gyroX, gyroY, gyroZ );
              IMU.readAcceleration( accelX, accelY, accelZ );
              // Convert gyro data to rps
              gyroY = gyroY * M_PI / 180 - 0.017;
              if (gyroY < 0.02 && gyroY > -0.02)
                gyroY = 0;
              accel_z_vec[i] = accelZ;
              gyro_y_vec[i] = gyroY;
              //Delay until time to take another measurement

              i++;
            }
          }
        }
        //Encode state data to transmit
        int state_accel = 0;
        int state_gyro = 0;
        for (int i = 0; i < 4; i++) {
          if (accel_z_vec[i] < 0 )
          {
            state_accel += (1 << i);
          }
          if (gyro_y_vec[i] < 0 )
          {
            state_gyro += (1 << i);
          }
        }

        //Convert state values from into to byte
        stateUnion.unionInt = state_accel;
        byte state_accel_byte = stateUnion.unionByte;
        stateUnion.unionInt = state_gyro;
        byte state_gyro_byte = stateUnion.unionByte;
        //Compile overall byte array

        message_bytes[0] = state_accel_byte;
        message_bytes[1] = state_gyro_byte;

        for (int i = 2; i <= 8; i += 2) {
          messageUnion.unionInt = abs(ceil(accel_z_vec[i / 2 - 1] * 1000));

          message_bytes[i] = messageUnion.unionBytes[0];
          message_bytes[i + 1] = messageUnion.unionBytes[1];
          messageUnion.unionInt = abs(ceil(gyro_y_vec[i / 2 - 1] * 100));

          message_bytes[i + 8] = messageUnion.unionBytes[0];
          message_bytes[i + 9] = messageUnion.unionBytes[1];
        }

        //Send data over ble
        ble_data.writeValue(message_bytes, sizeof message_bytes);

      }  // if millis
    } // while connected
  } // if central
} // loop
