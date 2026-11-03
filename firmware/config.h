/**
 * AquaSentinel - Active Hardware & Network Configuration
 * 
 * Configured for ESP32-WROOM-32E (Wi-Fi + Bluetooth Model)
 * and connected to AquaSentinal- Backend API (POST /api/v1/sensors/outlet).
 */

#ifndef CONFIG_H
#define CONFIG_H

#define FIRMWARE_VERSION            "0.1.0"
#define DEVICE_ID                   "AQUASENTINEL-01"
#define DEVICE_TOKEN                "test-device-secret-not-for-production"
#define DEFAULT_TEST_SESSION_ID     "SESSION-001"
#define DEFAULT_SAMPLE_TYPE         "OUTLET"

#define TDS_PIN                     34
#define TURBIDITY_PIN               35
#define DS18B20_PIN                 4
#define STATUS_LED_PIN              2
#define SAMPLE_SWITCH_PIN           0

#define TURBIDITY_VOLTAGE_DIVIDER_RATIO  1.00f
#define TDS_VOLTAGE_DIVIDER_RATIO        1.00f

#define SAMPLE_INTERVAL_MS          10000
#define ADC_SAMPLES_COUNT           30
#define ADC_SAMPLE_DELAY_US         1000

#define ENABLE_WIFI                 1
#define WIFI_SSID                   "YOUR_WIFI_SSID"
#define WIFI_PASSWORD               "YOUR_WIFI_PASSWORD"
#define BACKEND_READINGS_URL        "http://192.168.1.100:8000/api/v1/sensors/outlet"
#define HTTP_TIMEOUT_MS             4000
#define WIFI_RETRY_INTERVAL_MS      10000

#define NTP_SERVER_PRIMARY          "pool.ntp.org"
#define NTP_SERVER_SECONDARY        "time.nist.gov"

#define ENABLE_BLUETOOTH            1
#define BT_DEVICE_NAME              "AquaSentinel-ESP32E"

#define OFFLINE_QUEUE_SIZE          20

#endif // CONFIG_H

