#!/usr/bin/env python3
"""
AquaSentinel - Live USB / Bluetooth Serial to Backend Bridge.

Reads live telemetry directly from the ESP32-WROOM-32E over USB Serial (or Bluetooth SPP COM port)
and forwards each reading to the local AquaSentinel backend (POST /api/v1/sensors/outlet).
Ideal for bench testing when ESP32 Wi-Fi is disabled or on a different subnet.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
from datetime import datetime, timezone
import httpx
from dotenv import load_dotenv

load_dotenv()

DEFAULT_API_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000/api/v1/sensors/outlet")
DEFAULT_DEVICE_ID = "AQUASENTINEL-01"
DEFAULT_TOKEN = os.getenv("DEVICE_TOKENS", "").split("=")[-1] or "test-device-secret-not-for-production"


def forward_reading(client: httpx.Client, url: str, token: str, payload: dict) -> bool:
    headers = {
        "Content-Type": "application/json",
        "X-Device-Token": token
    }
    try:
        resp = client.post(url, json=payload, headers=headers, timeout=4.0)
        if resp.status_code == 201:
            print(f"[BRIDGE -> BACKEND] Accepted Seq #{payload['sequence']} (HTTP 201)")
            return True
        elif resp.status_code == 409:
            print(f"[BRIDGE -> BACKEND] Duplicate Seq #{payload['sequence']} (HTTP 409)")
            return False
        else:
            print(f"[BRIDGE -> BACKEND] Error HTTP {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        print(f"[BRIDGE -> BACKEND] HTTP Exception: {e}")
        return False


def run_bridge(port: str, baud: int, url: str, device_id: str, token: str):
    try:
        import serial
    except ImportError:
        print("[!] pyserial is required for the serial bridge. Install with: pip install pyserial")
        sys.exit(1)

    print(f"[*] Opening serial port: {port} at {baud} baud...")
    try:
        ser = serial.Serial(port, baud, timeout=1.0)
    except Exception as e:
        print(f"[!] Failed to open serial port {port}: {e}")
        return

    print(f"[*] Connected to {port}. Listening for ESP32 telemetry...")
    seq = 1

    current_tds_raw = 0
    current_tds_v = 0.0
    current_tds_ppm = 0.0
    current_turb_raw = 0
    current_turb_v = 0.0
    current_temp_c = None
    current_temp_valid = False

    with httpx.Client() as client:
        while True:
            try:
                line = ser.readline().decode("utf-8", errors="replace").strip()
                if not line:
                    continue

                print(f"[SERIAL] {line}")

                # Pattern matching telemetry lines from aquasentinel.ino
                # TDS: TDS Sensor: ADC = ... | Voltage = ... V | Est TDS = ... ppm
                tds_match = re.search(r"TDS Sensor:\s+ADC\s*=\s*(\d+)\s*\|\s*Voltage\s*=\s*([\d\.]+)\s*V(?:\s*\|\s*Est TDS\s*=\s*([\d\.]+))?", line)
                if tds_match:
                    current_tds_raw = int(tds_match.group(1))
                    current_tds_v = float(tds_match.group(2))
                    if tds_match.group(3):
                        current_tds_ppm = float(tds_match.group(3))

                # Turbidity: Turbidity: ADC = ... | Voltage = ... V
                turb_match = re.search(r"Turbidity:\s+ADC\s*=\s*(\d+)\s*\|\s*Voltage\s*=\s*([\d\.]+)\s*V", line)
                if turb_match:
                    current_turb_raw = int(turb_match.group(1))
                    current_turb_v = float(turb_match.group(2))

                # Temperature: Temperature: 25.50 °C [VALID]
                temp_match = re.search(r"Temperature:\s+([\d\.\-]+)\s*°C\s*\[VALID\]", line)
                if temp_match:
                    current_temp_c = float(temp_match.group(1))
                    current_temp_valid = True
                elif "DISCONNECTED" in line or "INVALID" in line:
                    current_temp_c = None
                    current_temp_valid = False

                # End of telemetry block delimiter
                if "--------------------------------------------------------------------------------" in line and (current_tds_v > 0 or current_turb_v > 0 or current_temp_valid):
                    timestamp_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                    payload = {
                        "schema_version": "1.0",
                        "device_id": device_id,
                        "sequence": seq,
                        "timestamp": timestamp_iso,
                        "measurement_point": "outlet",
                        "firmware_version": "0.1.0-bridge",
                        "outlet": {
                            "tds": {
                                "value": round(current_tds_ppm, 1),
                                "unit": "ppm",
                                "status": "valid",
                                "calibrated": False
                            },
                            "ph": {
                                "value": None,
                                "unit": "pH",
                                "status": "unavailable",
                                "calibrated": False
                            },
                            "turbidity": {
                                "value": round(current_turb_v, 3),
                                "unit": "raw",
                                "status": "valid",
                                "calibrated": False
                            },
                            "temperature": {
                                "value": current_temp_c,
                                "unit": "C",
                                "status": "valid" if current_temp_valid else "disconnected",
                                "calibrated": current_temp_valid
                            }
                        }
                    }
                    if forward_reading(client, url, token, payload):
                        seq += 1

            except KeyboardInterrupt:
                print("\n[*] Exiting bridge...")
                break
            except Exception as ex:
                print(f"[!] Error: {ex}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AquaSentinel Serial-to-Backend Bridge")
    parser.add_argument("--port", default="COM3", help="Serial COM port (e.g. COM3, COM4, /dev/ttyUSB0)")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200)")
    parser.add_argument("--url", default=DEFAULT_API_URL, help="Backend URL")
    parser.add_argument("--device-id", default=DEFAULT_DEVICE_ID, help="Device ID")
    parser.add_argument("--token", default=DEFAULT_TOKEN, help="Device token")
    args = parser.parse_args()

    run_bridge(args.port, args.baud, args.url, args.device_id, args.token)

