# AquaSentinel Hardware Wiring Guide: ESP32-WROOM-32E (Wi-Fi + BT)

This document provides complete, verified electrical wiring diagrams, pin assignments, and safety requirements for connecting the **DS18B20 temperature probe**, **Analog TDS sensor**, and **Turbidity sensor** to the **ESP32-WROOM-32E** development board.

---

## 1. Pin Assignment Summary

| Device / Module | Module Pin | ESP32-WROOM-32E Connection | Function / Electrical Notes |
| :--- | :--- | :--- | :--- |
| **Analog TDS Module** | `AOUT` / `AO` | **GPIO34** | ADC1_CH6 (Analog input only, Wi-Fi safe) |
| **Analog TDS Module** | `GND` | **GND** | Shared common system ground |
| **Analog TDS Module** | `VCC` | **3.3V** (or 5V/VIN via divider) | See Voltage Safety section below |
| **Turbidity Module** | `AOUT` / `AO` | **GPIO35** (via divider if 5V) | ADC1_CH7 (Analog input only, Wi-Fi safe) |
| **Turbidity Module** | `GND` | **GND** | Shared common system ground |
| **Turbidity Module** | `VCC` | **VIN / 5V** (or 3.3V if supported) | Typical optical modules require 5.0V |
| **DS18B20 Probe** | `DATA` (Yellow/White) | **GPIO4** | 1-Wire Digital Bus (Requires 4.7 kΩ pull-up) |
| **DS18B20 Probe** | `VDD` (Red) | **3.3V** | Powered directly from ESP32 3.3V rail |
| **DS18B20 Probe** | `GND` (Black) | **GND** | Shared common system ground |
| **4.7 kΩ Resistor** | Pin 1 to Pin 2 | **GPIO4 to 3.3V** | Mandatory pull-up resistor for 1-Wire bus |
| **Onboard Boot Button**| Internal | **GPIO0** | Active LOW, toggles INLET / OUTLET mode |
| **Onboard Status LED** | Internal | **GPIO2** | Status / Wi-Fi indicator LED |

---

## 2. Critical Architecture Details for ESP32-WROOM-32E

### Why ADC1 (GPIO34 & GPIO35) is Mandatory
The ESP32 SoC contains two separate Analog-to-Digital Converters:
- **ADC1:** Covers GPIO32, GPIO33, GPIO34, GPIO35, GPIO36 (VP), GPIO39 (VN).
- **ADC2:** Covers GPIO0, GPIO2, GPIO4, GPIO12, GPIO13, GPIO14, GPIO15, GPIO25, GPIO26, GPIO27.

> [!IMPORTANT]
> **ADC2 cannot be used when Wi-Fi is transmitting.** The Wi-Fi RF calibration engine takes exclusive control of ADC2. Attempting to read analog inputs on ADC2 while Wi-Fi is active will fail or return invalid readings.
> 
> AquaSentinel uses **GPIO34 (ADC1_CH6)** and **GPIO35 (ADC1_CH7)**, which operate seamlessly alongside Wi-Fi and Bluetooth on the ESP32-WROOM-32E.

---

## 3. Voltage Safety & Level Scaling (MANDATORY)

> [!CAUTION]
> **ESP32 GPIO pins are strictly 3.3V logic and are NOT 5V tolerant.**
> Applying more than 3.6V to any ESP32 pin will permanently damage the microcontroller.

### 3.1 Turbidity Sensor Voltage Scaling
Most analog turbidity signal-conditioning modules (e.g., TS-300B, DFRobot Gravity Turbidity clone) use an infrared photodiode/phototransistor optical pair that **requires 5.0V VCC** for proper sensitivity.
- In clean water (low turbidity), the phototransistor receives high infrared intensity, causing the analog output voltage ($V_{AO}$) to reach **4.1V to 4.5V**.
- **You MUST NOT connect this 4.5V output directly to GPIO35.**

#### Recommended Solution: Resistor Voltage Divider
Use two standard resistors ($R_1 = 10\text{ k}\Omega$ and $R_2 = 20\text{ k}\Omega$, or $R_1 = 1\text{ k}\Omega$ and $R_2 = 2\text{ k}\Omega$):

```
 Turbidity Module AO (0 - 4.5V)
          │
          │
         ┌┴┐
         │ │ R1 (10 kΩ, 1%)
         └┬┘
          │
          ├──────────────> To ESP32 GPIO35 (ADC1_CH7) [Max ~3.0V]
          │
         ┌┴┐
         │ │ R2 (20 kΩ, 1%)
         └┬┘
          │
         GND (Shared)
```

$$\text{Voltage Ratio} = \frac{R_2}{R_1 + R_2} = \frac{20\text{ k}\Omega}{10\text{ k}\Omega + 20\text{ k}\Omega} = \frac{2}{3} \approx 0.667$$

$$V_{\text{ESP32}} = 4.5\text{ V} \times 0.667 = 3.0\text{ V} \quad (\text{Safe for 3.3V ESP32 ADC})$$

*In `firmware/config.h`, set `TURBIDITY_VOLTAGE_DIVIDER_RATIO` to `1.50f` to scale the measured ADC voltage back to the sensor's true output voltage.*

---

### 3.2 TDS Sensor Module
Most modern analog TDS modules (e.g., Keyestudio, DFRobot Gravity TDS) feature an onboard regulator allowing operation at **3.3V or 5V**:
- **Preferred wiring:** Power the TDS module's $V_{CC}$ from the ESP32's **3.3V** rail. Its output will range from $0\text{ V}$ to $\sim 2.3\text{ V}$, which connects safely and directly to **GPIO34** with **no voltage divider required** (`TDS_VOLTAGE_DIVIDER_RATIO = 1.00f`).
- **If module requires 5V:** Verify with a multimeter under high-salinity water. If output exceeds 3.1V, insert a voltage divider identical to the turbidity module.

---

### 3.3 DS18B20 Waterproof Temperature Probe
The DS18B20 digital thermometer communicates over the Maxim Dallas 1-Wire protocol:
- **Power:** Connect VDD to the ESP32 **3.3V** pin and GND to **GND**.
- **Pull-up Resistor:** The 1-Wire bus requires an external pull-up resistor. Connect a **4.7 kΩ** resistor between the **DATA pin (GPIO4)** and the **3.3V rail**.
- **Wire Colors (Common Standard):**
  - **Red:** $V_{DD}$ (3.3V)
  - **Black:** GND
  - **Yellow or White:** DATA (GPIO4)
  *(Warning: Verify your probe's datasheet or label, as third-party probes occasionally use non-standard colors).*

```
                     3.3V Rail
                        │
                        ├─────────────┐
                        │             │
                       ┌┴┐           ┌┴┐
         DS18B20 VDD   │ │           │ │ 4.7 kΩ Pull-up Resistor
         (Red wire)    └┬┘           └┬┘
                        │             │
                        │             ├────────> ESP32 GPIO4 (DATA)
                        │             │          (Yellow/White wire)
                        │            ┌┴┐
                       GND           │ │ DS18B20 GND (Black wire)
                                     └┬┘
                                      │
                                     GND
```

---

## 4. Pre-Power Multimeter Verification Checklist

Before inserting any signal wire into the ESP32 board headers, complete this 5-step checklist:

1. [ ] **Common Ground:** Confirm with a continuity multimeter check that the ESP32 GND, TDS GND, and Turbidity GND are all tied to the same reference.
2. [ ] **DS18B20 Voltage:** Measure voltage between DS18B20 DATA and GND with probe connected; it should read steady $\approx 3.3\text{ V}$ (pulled high).
3. [ ] **TDS Output Verification:** Dip TDS probe in clean water. Measure voltage between TDS AO and GND with a DMM. Confirm reading is $< 3.1\text{ V}$.
4. [ ] **Turbidity Output Verification:** Place turbidity sensor in clean tap water with sensor powered. Measure voltage at the voltage divider output (point connected to GPIO35). Confirm reading is $< 3.1\text{ V}$.
5. [ ] **Connection:** Only after steps 1–4 are confirmed, connect GPIO34 and GPIO35 to their respective signal lines.

---

## 5. Physical Setup and Water Safety

- **Sample Chamber Separation:** The ESP32 board, breadboard, level shifters, and power supply must be located in a **dry enclosure or raised dry zone**, physically separated from the water sample container.
- **Probe Immersion Depth:**
  - **DS18B20:** The stainless steel tube is waterproof. Submerge only the metallic probe and lower insulated cable. Do not submerge the terminal ends.
  - **TDS Probe:** Submerge only the two exposed electrode prongs and black plastic probe tip. The cable junction must stay dry.
  - **Turbidity Sensor:** The optical fork is water-resistant. **Never submerge the small rectangular amplifier/signal conditioning PCB!** Only the optical probe tip contacts the liquid.
- **Rinsing & Cleaning:** When alternating between `INLET` (tap/raw water) and `OUTLET` (purified RO water), thoroughly rinse all probes with distilled or deionized water and gently blot dry with a lint-free wipe. Residual droplets will contaminate low-TDS outlet readings.

