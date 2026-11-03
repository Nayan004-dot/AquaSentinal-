/**
 * ============================================================================
 * Project: AquaSentinel - Water Quality Monitoring & RO Performance Analysis
 * File:    aquasentinel.ino
 * Target:  ESP32-WROOM-32E (Wi-Fi + Bluetooth Model)
 * Purpose: Multi-sensor acquisition (TDS, Turbidity, DS18B20) with Serial,
 *          Wi-Fi HTTP transmission to AquaSentinel Backend API (v1.0 schema),
 *          and Bluetooth Serial telemetry.
 * ============================================================================
 */

#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <ArduinoJson.h>
#include <time.h>

// Configuration header (pins, Wi-Fi credentials, tokens, session info)
#if __has_include("config.h")
  #include "config.h"
#elif __has_include("config.example.h")
  #include "config.example.h"
#else
  #error "Missing config.h or config.example.h! Please create firmware/config.h"
#endif

// Optional Bluetooth Serial for ESP32-WROOM-32E (Wi-Fi + BT Classic)
#if ENABLE_BLUETOOTH
  #include <BluetoothSerial.h>
  #if !defined(CONFIG_BT_ENABLED) || !defined(CONFIG_BLUEDROID_ENABLED)
    #error "Bluetooth is not enabled in board configuration! Disable ENABLE_BLUETOOTH or use a BT-compatible board."
  #endif
  BluetoothSerial SerialBT;
#endif

// ============================================================================
// DATA STRUCTURES
// ============================================================================
struct SensorRecord {
  uint32_t sequence;
  char     timestamp_iso[32];
  uint16_t tds_adc_raw;
  float    tds_voltage_v;
  float    tds_estimated_ppm;
  uint16_t turbidity_adc_raw;
  float    turbidity_voltage_v;
  float    temperature_c;
  bool     temperature_valid;
  char     sample_type[10];      // "OUTLET" (contract) or "INLET"
};

// ============================================================================
// GLOBAL STATE & PERIPHERALS
// ============================================================================
OneWire oneWire(DS18B20_PIN);
DallasTemperature dallasSensors(&oneWire);

// Active runtime state
String currentSampleType   = DEFAULT_SAMPLE_TYPE;
uint32_t telemetrySequence = 1;
unsigned long lastSampleTime = 0;
unsigned long lastTempRequestTime = 0;
bool tempConversionPending = false;
bool ntpSynced = false;

// Button debouncing for BOOT button (GPIO 0) sample mode toggling
int lastButtonState = HIGH;
unsigned long lastDebounceTime = 0;
const unsigned long DEBOUNCE_DELAY_MS = 50;

// Wi-Fi state tracking
unsigned long lastWifiRetryTime = 0;
bool wifiConnected = false;

// Volatile RAM queue for offline buffering during Wi-Fi dropouts
#if OFFLINE_QUEUE_SIZE > 0
SensorRecord offlineQueue[OFFLINE_QUEUE_SIZE];
int queueHead = 0;
int queueTail = 0;
int queueCount = 0;
#endif

// ============================================================================
// HELPER FOR UNIFIED LOGGING (USB Serial + Optional Bluetooth)
// ============================================================================
void logPrint(const String &msg) {
  Serial.print(msg);
#if ENABLE_BLUETOOTH
  if (SerialBT.hasClient()) {
    SerialBT.print(msg);
  }
#endif
}

void logPrintln(const String &msg = "") {
  Serial.println(msg);
#if ENABLE_BLUETOOTH
  if (SerialBT.hasClient()) {
    SerialBT.println(msg);
  }
#endif
}

// ============================================================================
// TIME & ISO-8601 TIMESTAMP GENERATION
// ============================================================================
void initNtpTime() {
  logPrintln("[NTP] Configuring time via SNTP (" NTP_SERVER_PRIMARY ")...");
  // Set to UTC (offset 0, daylight 0) as required by Backend ISO-8601 Z format
  configTime(0, 0, NTP_SERVER_PRIMARY, NTP_SERVER_SECONDARY);
}

void getIsoTimestamp(char *buffer, size_t maxLen) {
  time_t now;
  time(&now);
  struct tm timeinfo;

  if (now > 1700000000) { // Year 2023+ indicates valid NTP sync
    gmtime_r(&now, &timeinfo);
    strftime(buffer, maxLen, "%Y-%m-%dT%H:%M:%SZ", &timeinfo);
    ntpSynced = true;
  } else {
    // Fallback relative ISO timestamp if NTP has not yet acquired lock
    unsigned long sec = millis() / 1000;
    snprintf(buffer, maxLen, "2026-11-03T%02lu:%02lu:%02luZ",
             (sec / 3600) % 24, (sec / 60) % 60, sec % 60);
  }
}

// ============================================================================
// OFFLINE QUEUE MANAGEMENT
// ============================================================================
bool queuePush(const SensorRecord &record) {
#if OFFLINE_QUEUE_SIZE > 0
  if (queueCount >= OFFLINE_QUEUE_SIZE) {
    queueHead = (queueHead + 1) % OFFLINE_QUEUE_SIZE;
    queueCount--;
    logPrintln("[QUEUE] Buffer full! Dropping oldest reading.");
  }
  offlineQueue[queueTail] = record;
  queueTail = (queueTail + 1) % OFFLINE_QUEUE_SIZE;
  queueCount++;
  return true;
#else
  return false;
#endif
}

bool queuePop(SensorRecord &record) {
#if OFFLINE_QUEUE_SIZE > 0
  if (queueCount <= 0) return false;
  record = offlineQueue[queueHead];
  queueHead = (queueHead + 1) % OFFLINE_QUEUE_SIZE;
  queueCount--;
  return true;
#else
  return false;
#endif
}

// ============================================================================
// ADC FILTERING: Median & Calibrated Voltage Acquisition
// ============================================================================
void readFilteredAdc(uint8_t pin, float dividerRatio, uint16_t &rawMedian, float &voltageMedian) {
  uint16_t rawSamples[ADC_SAMPLES_COUNT];
  uint32_t mvSamples[ADC_SAMPLES_COUNT];

  // 1. Collect over-samples with small delay to suppress 50/60Hz noise
  for (int i = 0; i < ADC_SAMPLES_COUNT; i++) {
    rawSamples[i] = analogRead(pin);
    mvSamples[i]  = analogReadMilliVolts(pin);
    delayMicroseconds(ADC_SAMPLE_DELAY_US);
  }

  // 2. Insertion sort to obtain median
  for (int i = 1; i < ADC_SAMPLES_COUNT; i++) {
    uint16_t rawKey = rawSamples[i];
    uint32_t mvKey  = mvSamples[i];
    int j = i - 1;
    while (j >= 0 && rawSamples[j] > rawKey) {
      rawSamples[j + 1] = rawSamples[j];
      mvSamples[j + 1]  = mvSamples[j];
      j--;
    }
    rawSamples[j + 1] = rawKey;
    mvSamples[j + 1]  = mvKey;
  }

  int midIndex = ADC_SAMPLES_COUNT / 2;
  rawMedian = rawSamples[midIndex];
  voltageMedian = (static_cast<float>(mvSamples[midIndex]) / 1000.0f) * dividerRatio;
}

// Calculate temperature-compensated estimated TDS in ppm
float estimateTdsPpm(float voltage, float tempC, bool tempValid) {
  if (voltage < 0.03f) return 0.0f;
  float referenceTemp = tempValid ? tempC : 25.0f;
  // Standard 2%/°C temperature compensation
  float compensationCoefficient = 1.0f + 0.02f * (referenceTemp - 25.0f);
  float compensationVoltage = voltage / compensationCoefficient;
  // Standard polynomial curve for TDS analog probes
  float tds = (133.42f * pow(compensationVoltage, 3) - 
               255.86f * pow(compensationVoltage, 2) + 
               857.39f * compensationVoltage) * 0.5f;
  return max(0.0f, tds);
}

// ============================================================================
// TEMPERATURE ACQUISITION & VALIDATION (Non-blocking DS18B20)
// ============================================================================
void startTemperatureConversion() {
  dallasSensors.requestTemperatures();
  lastTempRequestTime = millis();
  tempConversionPending = true;
}

float readTemperature(bool &isValid) {
  float tempC = dallasSensors.getTempCByIndex(0);
  if (tempC == DEVICE_DISCONNECTED_C || tempC == 85.0f || tempC < -5.0f || tempC > 80.0f) {
    isValid = false;
  } else {
    isValid = true;
  }
  return tempC;
}

// ============================================================================
// WI-FI & HTTP TRANSMISSION (AquaSentinel V1 API Specification)
// ============================================================================
void handleWiFiConnection() {
#if ENABLE_WIFI
  if (WiFi.status() == WL_CONNECTED) {
    if (!wifiConnected) {
      wifiConnected = true;
      logPrintln("[WIFI] Connected! IP Address: " + WiFi.localIP().toString() + 
                 " (RSSI: " + String(WiFi.RSSI()) + " dBm)");
      digitalWrite(STATUS_LED_PIN, HIGH);
      initNtpTime();
    }
  } else {
    if (wifiConnected) {
      wifiConnected = false;
      logPrintln("[WIFI] Connection lost! Entering offline buffering mode.");
      digitalWrite(STATUS_LED_PIN, LOW);
    }
    if (millis() - lastWifiRetryTime >= WIFI_RETRY_INTERVAL_MS) {
      lastWifiRetryTime = millis();
      logPrintln("[WIFI] Attempting connection to SSID: " + String(WIFI_SSID) + "...");
      WiFi.disconnect();
      WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    }
  }
#endif
}

bool sendReadingToBackend(const SensorRecord &record) {
#if ENABLE_WIFI
  if (WiFi.status() != WL_CONNECTED) {
    return false;
  }

  HTTPClient http;
  http.begin(BACKEND_READINGS_URL);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-Token", DEVICE_TOKEN);
  http.setTimeout(HTTP_TIMEOUT_MS);

  // Build JSON payload strictly adhering to contracts/outlet_sensor_telemetry.schema.json
  #if ARDUINOJSON_VERSION_MAJOR >= 7
    JsonDocument doc;
  #else
    StaticJsonDocument<768> doc;
  #endif

  doc["schema_version"]    = "1.0";
  doc["device_id"]         = DEVICE_ID;
  doc["sequence"]          = record.sequence;
  doc["timestamp"]         = record.timestamp_iso;
  doc["measurement_point"] = "outlet";
  doc["firmware_version"]  = FIRMWARE_VERSION;

  JsonObject outlet = doc["outlet"].to<JsonObject>();

  // TDS Measurement (unit: "ppm")
  JsonObject tdsObj = outlet["tds"].to<JsonObject>();
  tdsObj["value"]      = serialized(String(record.tds_estimated_ppm, 1));
  tdsObj["unit"]       = "ppm";
  tdsObj["status"]     = "valid";
  tdsObj["calibrated"] = false;

  // pH Measurement (not fitted on hardware prototype: status unavailable)
  JsonObject phObj = outlet["ph"].to<JsonObject>();
  phObj["value"]      = nullptr;
  phObj["unit"]       = "pH";
  phObj["status"]     = "unavailable";
  phObj["calibrated"] = false;

  // Turbidity Measurement (unit: "raw" voltage)
  JsonObject turbObj = outlet["turbidity"].to<JsonObject>();
  turbObj["value"]      = serialized(String(record.turbidity_voltage_v, 3));
  turbObj["unit"]       = "raw";
  turbObj["status"]     = "valid";
  turbObj["calibrated"] = false;

  // Temperature Measurement (unit: "C")
  JsonObject tempObj = outlet["temperature"].to<JsonObject>();
  if (record.temperature_valid) {
    tempObj["value"]      = serialized(String(record.temperature_c, 2));
    tempObj["status"]     = "valid";
    tempObj["calibrated"] = true;
  } else {
    tempObj["value"]      = nullptr;
    tempObj["status"]     = "disconnected";
    tempObj["calibrated"] = false;
  }
  tempObj["unit"] = "C";

  String jsonPayload;
  serializeJson(doc, jsonPayload);

  int httpResponseCode = http.POST(jsonPayload);
  bool success = false;

  if (httpResponseCode > 0) {
    if (httpResponseCode == HTTP_CODE_OK || httpResponseCode == HTTP_CODE_CREATED) {
      logPrintln("[HTTP] POST Accepted (HTTP " + String(httpResponseCode) + ") | Seq #" + String(record.sequence));
      success = true;
    } else if (httpResponseCode == 409) {
      logPrintln("[HTTP] Duplicate sequence rejected (HTTP 409). Advancing sequence.");
      success = true; // Count as processed so we advance sequence
    } else {
      logPrintln("[HTTP] POST Failed (HTTP " + String(httpResponseCode) + "): " + http.getString());
    }
  } else {
    logPrintln("[HTTP] POST Error: " + http.errorToString(httpResponseCode));
  }

  http.end();
  return success;
#else
  return false;
#endif
}

void flushOfflineQueue() {
#if OFFLINE_QUEUE_SIZE > 0 && ENABLE_WIFI
  if (WiFi.status() == WL_CONNECTED && queueCount > 0) {
    logPrintln("[QUEUE] Flushing " + String(queueCount) + " buffered records to backend...");
    while (queueCount > 0) {
      SensorRecord bufferedRecord;
      if (queuePop(bufferedRecord)) {
        if (!sendReadingToBackend(bufferedRecord)) {
          queuePush(bufferedRecord);
          logPrintln("[QUEUE] Transmission failed during flush. Buffer retained.");
          break;
        }
        delay(60);
      }
    }
  }
#endif
}

// ============================================================================
// USER INTERACTION (BOOT Button & Serial/Bluetooth Commands)
// ============================================================================
void toggleSampleMode() {
  if (currentSampleType == "INLET") {
    currentSampleType = "OUTLET";
  } else {
    currentSampleType = "INLET";
  }
  logPrintln();
  logPrintln("==================================================");
  logPrintln(">>> SAMPLE TYPE SWITCHED TO: [" + currentSampleType + "] <<<");
  logPrintln("==================================================");
  logPrintln();

  digitalWrite(STATUS_LED_PIN, LOW);
  delay(100);
  digitalWrite(STATUS_LED_PIN, HIGH);
  delay(100);
  digitalWrite(STATUS_LED_PIN, LOW);
  delay(100);
  digitalWrite(STATUS_LED_PIN, HIGH);
}

void handleButtonInput() {
  int reading = digitalRead(SAMPLE_SWITCH_PIN);
  if (reading != lastButtonState) {
    lastDebounceTime = millis();
  }

  if ((millis() - lastDebounceTime) > DEBOUNCE_DELAY_MS) {
    static int buttonState = HIGH;
    if (reading != buttonState) {
      buttonState = reading;
      if (buttonState == LOW) {
        toggleSampleMode();
      }
    }
  }
  lastButtonState = reading;
}

void handleCommand(char cmd) {
  switch (cmd) {
    case 'i':
    case 'I':
      currentSampleType = "INLET";
      logPrintln("[MODE] Sample set to: INLET");
      break;
    case 'o':
    case 'O':
      currentSampleType = "OUTLET";
      logPrintln("[MODE] Sample set to: OUTLET");
      break;
    case 's':
    case 'S':
      logPrintln();
      logPrintln("--- AquaSentinel Status ---");
      logPrintln("Device ID:        " + String(DEVICE_ID));
      logPrintln("Firmware Version: " + String(FIRMWARE_VERSION));
      logPrintln("Sequence Number:  " + String(telemetrySequence));
      logPrintln("Active Sample:    " + currentSampleType);
      logPrintln("Wi-Fi Status:     " + String(WiFi.status() == WL_CONNECTED ? "Connected" : "Disconnected"));
      logPrintln("NTP Synced:       " + String(ntpSynced ? "Yes (UTC)" : "Pending"));
#if OFFLINE_QUEUE_SIZE > 0
      logPrintln("Queued Records:   " + String(queueCount) + "/" + String(OFFLINE_QUEUE_SIZE));
#endif
      logPrintln("---------------------------");
      break;
    case 'h':
    case 'H':
    case '?':
      logPrintln();
      logPrintln("--- AquaSentinel Commands ---");
      logPrintln("  I / i : Select INLET mode");
      logPrintln("  O / o : Select OUTLET mode");
      logPrintln("  S / s : Print status summary");
      logPrintln("  H / h : Print help menu");
      logPrintln("  BOOT  : Press on-board button (GPIO 0) to toggle INLET/OUTLET");
      logPrintln("-----------------------------");
      break;
    default:
      break;
  }
}

void handleSerialAndBluetoothInput() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c != '\r' && c != '\n') {
      handleCommand(c);
    }
  }

#if ENABLE_BLUETOOTH
  while (SerialBT.available()) {
    char c = SerialBT.read();
    if (c != '\r' && c != '\n') {
      handleCommand(c);
    }
  }
#endif
}

// ============================================================================
// FORMATTED TELEMETRY OUTPUT
// ============================================================================
void printReadingTelemetry(const SensorRecord &record) {
  logPrintln();
  logPrintln("--------------------------------------------------------------------------------");
  logPrintln("AquaSentinel ESP32-E Telemetry | Seq #" + String(record.sequence) + 
             " | Time: " + String(record.timestamp_iso));
  logPrintln("Sample Point:    [" + String(record.sample_type) + "] | Device: " + String(DEVICE_ID));
  logPrintln("--------------------------------------------------------------------------------");

  // TDS Sensor
  logPrint("TDS Sensor:      ADC = " + String(record.tds_adc_raw) + 
           " | Voltage = " + String(record.tds_voltage_v, 3) + 
           " V | Est TDS = " + String(record.tds_estimated_ppm, 1) + " ppm");
  if (record.tds_adc_raw >= 4090) {
    logPrint(" [!] SATURATION");
  }
  logPrintln();

  // Turbidity Sensor
  logPrint("Turbidity:       ADC = " + String(record.turbidity_adc_raw) + 
           " | Voltage = " + String(record.turbidity_voltage_v, 3) + " V (raw optical)");
  if (record.turbidity_adc_raw >= 4090) {
    logPrint(" [!] SATURATION");
  }
  logPrintln();

  // DS18B20 Temperature
  if (record.temperature_valid) {
    logPrintln("Temperature:     " + String(record.temperature_c, 2) + " °C [VALID]");
  } else {
    logPrintln("Temperature:     DISCONNECTED / ERROR [INVALID]");
  }

  // Network & Queue Status
  String netStatus = (WiFi.status() == WL_CONNECTED) ? "ONLINE" : "OFFLINE";
#if OFFLINE_QUEUE_SIZE > 0
  logPrintln("Backend Link:    " + netStatus + " | Endpoint: " BACKEND_READINGS_URL + 
             " | RAM Queue: " + String(queueCount) + "/" + String(OFFLINE_QUEUE_SIZE));
#else
  logPrintln("Backend Link:    " + netStatus + " | Endpoint: " BACKEND_READINGS_URL);
#endif
  logPrintln("--------------------------------------------------------------------------------");
}

// ============================================================================
// MAIN SETUP
// ============================================================================
void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println();
  Serial.println("================================================================================");
  Serial.println("   AquaSentinel - ESP32-WROOM-32E Connected Node");
  Serial.println("   Version: " FIRMWARE_VERSION " | Device ID: " DEVICE_ID);
  Serial.println("   Target API: " BACKEND_READINGS_URL);
  Serial.println("================================================================================");

  pinMode(STATUS_LED_PIN, OUTPUT);
  digitalWrite(STATUS_LED_PIN, LOW);
  pinMode(SAMPLE_SWITCH_PIN, INPUT_PULLUP);

  analogReadResolution(12);
  analogSetAttenuation(ADC_11db);
  analogSetPinAttenuation(TDS_PIN, ADC_11db);
  analogSetPinAttenuation(TURBIDITY_PIN, ADC_11db);
  Serial.println("[ADC] Configured 12-bit ADC on GPIO" + String(TDS_PIN) + " & GPIO" + String(TURBIDITY_PIN));

  dallasSensors.begin();
  dallasSensors.setWaitForConversion(false);
  dallasSensors.setResolution(12);
  startTemperatureConversion();
  Serial.println("[DS18B20] Dallas temperature sensor initialized on GPIO" + String(DS18B20_PIN));

#if ENABLE_BLUETOOTH
  if (SerialBT.begin(BT_DEVICE_NAME)) {
    Serial.println("[BLUETOOTH] Bluetooth Serial started as \"" BT_DEVICE_NAME "\"");
  } else {
    Serial.println("[BLUETOOTH] Bluetooth initialization failed!");
  }
#endif

#if ENABLE_WIFI
  WiFi.mode(WIFI_STA);
  Serial.println("[WIFI] Connecting to SSID: " + String(WIFI_SSID) + "...");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  lastWifiRetryTime = millis();
#endif

  Serial.println();
  Serial.println("[READY] Sampling every " + String(SAMPLE_INTERVAL_MS / 1000) + " seconds.");
  Serial.println("================================================================================");
}

// ============================================================================
// MAIN LOOP
// ============================================================================
void loop() {
  unsigned long currentMillis = millis();

  // 1. Process inputs
  handleButtonInput();
  handleSerialAndBluetoothInput();

  // 2. Wi-Fi background handling
  handleWiFiConnection();

  // 3. Periodic sensor acquisition
  if (currentMillis - lastSampleTime >= SAMPLE_INTERVAL_MS) {
    lastSampleTime = currentMillis;

    // A. Temperature read & restart conversion
    bool tempValid = false;
    float tempC = readTemperature(tempValid);
    startTemperatureConversion();

    // B. TDS ADC & voltage
    uint16_t tdsRaw = 0;
    float tdsVoltage = 0.0f;
    readFilteredAdc(TDS_PIN, TDS_VOLTAGE_DIVIDER_RATIO, tdsRaw, tdsVoltage);
    float tdsEstimatedPpm = estimateTdsPpm(tdsVoltage, tempC, tempValid);

    // C. Turbidity ADC & voltage
    uint16_t turbRaw = 0;
    float turbVoltage = 0.0f;
    readFilteredAdc(TURBIDITY_PIN, TURBIDITY_VOLTAGE_DIVIDER_RATIO, turbRaw, turbVoltage);

    // D. Build SensorRecord
    SensorRecord record;
    record.sequence             = telemetrySequence;
    getIsoTimestamp(record.timestamp_iso, sizeof(record.timestamp_iso));
    record.tds_adc_raw          = tdsRaw;
    record.tds_voltage_v        = tdsVoltage;
    record.tds_estimated_ppm    = tdsEstimatedPpm;
    record.turbidity_adc_raw    = turbRaw;
    record.turbidity_voltage_v  = turbVoltage;
    record.temperature_c        = tempC;
    record.temperature_valid    = tempValid;
    strncpy(record.sample_type, currentSampleType.c_str(), sizeof(record.sample_type) - 1);
    record.sample_type[sizeof(record.sample_type) - 1] = '\0';

    // E. Print Telemetry
    printReadingTelemetry(record);

    // F. Transmit to backend
#if ENABLE_WIFI
    if (WiFi.status() == WL_CONNECTED) {
      flushOfflineQueue();
      if (!sendReadingToBackend(record)) {
        queuePush(record);
      }
    } else {
      queuePush(record);
    }
#endif

    // Advance sequence number for next reading
    telemetrySequence++;
  }
}
