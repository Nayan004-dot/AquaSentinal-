#!/usr/bin/env python3
"""
AquaSentinel - Telemetry Simulator for Testing Pipeline Integration.

Generates realistic outlet sensor readings according to contracts/outlet_sensor_telemetry.schema.json
and transmits them to the AquaSentinel FastAPI backend via POST /api/v1/sensors/outlet.
"""
from __future__ import annotations

import argparse
import os
import random
import time
from datetime import datetime, timezone
import httpx
from dotenv import load_dotenv

# Load configuration from .env
load_dotenv()

DEFAULT_API_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000/api/v1/sensors/outlet")
DEFAULT_DEVICE_ID = "AQUASENTINEL-01"
DEFAULT_TOKEN = os.getenv("DEVICE_TOKENS", "").split("=")[-1] or "test-device-secret-not-for-production"


def generate_reading(device_id: str, sequence: int, base_tds: float = 120.0, base_turb: float = 1.8, base_temp: float = 25.5) -> dict:
    """Generate a single valid reading according to the contract."""
    # Slight random drift simulating realistic water sample variation
    tds_val = round(base_tds + random.uniform(-2.5, 2.5), 1)
    turb_val = round(max(0.1, base_turb + random.uniform(-0.05, 0.05)), 3)
    temp_val = round(base_temp + random.uniform(-0.2, 0.2), 2)
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return {
        "schema_version": "1.0",
        "device_id": device_id,
        "sequence": sequence,
        "timestamp": now_iso,
        "measurement_point": "outlet",
        "firmware_version": "0.1.0-sim",
        "outlet": {
            "tds": {
                "value": tds_val,
                "unit": "ppm",
                "status": "valid",
                "calibrated": True
            },
            "ph": {
                "value": None,
                "unit": "pH",
                "status": "unavailable",
                "calibrated": False
            },
            "turbidity": {
                "value": turb_val,
                "unit": "raw",
                "status": "valid",
                "calibrated": False
            },
            "temperature": {
                "value": temp_val,
                "unit": "C",
                "status": "valid",
                "calibrated": True
            }
        }
    }


def main():
    parser = argparse.ArgumentParser(description="AquaSentinel Live Telemetry Simulator")
    parser.add_argument("--url", default=DEFAULT_API_URL, help=f"Backend endpoint (default: {DEFAULT_API_URL})")
    parser.add_argument("--device-id", default=DEFAULT_DEVICE_ID, help=f"Device ID (default: {DEFAULT_DEVICE_ID})")
    parser.add_argument("--token", default=DEFAULT_TOKEN, help="X-Device-Token secret")
    parser.add_argument("--count", type=int, default=10, help="Number of telemetry samples to transmit (default: 10, 0 for infinite)")
    parser.add_argument("--interval", type=float, default=2.0, help="Interval between samples in seconds (default: 2.0)")
    args = parser.parse_args()

    print(f"[*] Starting AquaSentinel Simulator")
    print(f"[*] Endpoint:  {args.url}")
    print(f"[*] Device ID: {args.device_id}")
    print(f"[*] Interval:  {args.interval}s")
    print("-" * 60)

    seq = 1
    # Check latest sequence from database/backend if possible
    try:
        latest_url = args.url.replace("/sensors/outlet", "/outlet/latest")
        resp = httpx.get(latest_url, params={"device_id": args.device_id}, timeout=3.0)
        if resp.status_code == 200 and resp.json().get("data_status") == "available":
            # Start beyond latest sequence
            history_url = args.url.replace("/sensors/outlet", "/outlet/history")
            now = datetime.now(timezone.utc)
            h_resp = httpx.get(history_url, params={
                "device_id": args.device_id,
                "from": "2020-01-01T00:00:00Z",
                "to": "2030-01-01T00:00:00Z",
                "limit": 1000
            }, timeout=3.0)
            if h_resp.status_code == 200 and h_resp.json().get("items"):
                max_seq = max(item["sequence"] for item in h_resp.json()["items"])
                seq = max_seq + 1
                print(f"[*] Resuming from sequence #{seq}")
    except Exception:
        pass

    sent = 0
    with httpx.Client(timeout=5.0) as client:
        while True:
            payload = generate_reading(args.device_id, seq)
            headers = {
                "Content-Type": "application/json",
                "X-Device-Token": args.token
            }
            try:
                r = client.post(args.url, json=payload, headers=headers)
                if r.status_code == 201:
                    print(f"[{payload['timestamp']}] Sent Seq #{seq}: TDS={payload['outlet']['tds']['value']} ppm, "
                          f"Turb={payload['outlet']['turbidity']['value']} V, Temp={payload['outlet']['temperature']['value']} °C -> HTTP 201 Created")
                    seq += 1
                    sent += 1
                elif r.status_code == 409:
                    print(f"[!] Sequence #{seq} already exists (HTTP 409). Advancing sequence...")
                    seq += 1
                else:
                    print(f"[!] POST Failed: HTTP {r.status_code} - {r.text}")
            except Exception as e:
                print(f"[!] Connection error: {e}")

            if args.count > 0 and sent >= args.count:
                print(f"[*] Finished transmitting {sent} samples.")
                break

            time.sleep(args.interval)


if __name__ == "__main__":
    main()

