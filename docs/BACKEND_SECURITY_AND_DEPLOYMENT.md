# AquaSentinel Backend Security and Deployment

## 1. Local service

- Backend host: Person 1's Ubuntu laptop.
- Framework: FastAPI.
- Database: SQLite for the first prototype.
- Development port: `8000` unless configured otherwise.
- Keep the API bound to `127.0.0.1` when the tunnel process runs on the same laptop and forwards to it. This avoids exposing the development server directly on every network interface.

Typical development command (adjust package path to the implemented layout):

```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

## 2. Remote access

Use a secure outbound tunnel (planned: Cloudflare Tunnel) from the laptop to a public HTTPS hostname.

```text
ESP32 / Browser
      |
      | HTTPS to public API hostname
      v
Tunnel provider edge
      |
      | existing outbound tunnel connection
      v
127.0.0.1:8000 on Person 1's laptop
```

The ESP32 and dashboard may be on different networks. They do not need to share Wi-Fi with the laptop once the public hostname is configured.

The laptop, FastAPI process and tunnel must remain powered/running and have internet connectivity. If they are offline, ingestion and dashboard API calls are unavailable. ESP32 should retry with backoff and may keep a bounded local queue of unsent readings.

Use a temporary tunnel URL for development only. For a stable demonstration/deployment hostname, use a properly configured named tunnel and domain. The public URL is not an authentication mechanism.

## 3. Authentication and secrets

- Give each ESP32 device its own token.
- Send token in an HTTPS header such as `X-Device-Token`.
- Store accepted token hashes or use a secure secret store/environment configuration; never store plaintext token in Git.
- Do not commit `.env`, Wi-Fi credentials, Cloudflare credentials, device tokens or private keys.
- Provide `.env.example` containing placeholder names only.
- Rotate a token if it is exposed.
- Dashboard access must also be considered before exposing read endpoints publicly. Add suitable access control if readings are not intended to be public.

## 4. Request and application security

- Enforce JSON content type and a small maximum payload size.
- Validate schema, numeric finiteness, allowed units, statuses, timestamps and device authorization.
- Apply rate limiting to ingestion.
- Use a restrictive CORS allowlist for the deployed dashboard origin; do not use wildcard origins with credentials.
- Do not expose interactive API documentation publicly in production unless protected.
- Do not expose raw CSV files, the SQLite database file, local filesystem paths, debug stack traces or admin operations.
- Use parameterized database operations/ORM; never build SQL from untrusted input.
- Keep logging useful but do not log device tokens.

## 5. Availability and data integrity

- Enable SQLite transactions and appropriate backup practice.
- Use a unique `(device_id, sequence)` constraint for deduplication.
- Keep server receipt time as well as device capture time.
- Define device stale timeout and late-arrival handling.
- Use idempotent aggregation and recover closed windows on startup.
- Return clear 4xx/5xx errors so ESP32 can distinguish invalid requests from retryable server/network failures.
- Never treat network outage or missing sensor data as a normal reading.

## 6. Deployment test

1. Start FastAPI on laptop.
2. Start tunnel to local FastAPI port.
3. From a separate network, call public `/api/v1/health`.
4. Send an authenticated test sensor request from ESP32 or curl.
5. Confirm database row and acknowledgement.
6. Query latest/history/summary endpoints from another network.
7. Stop the tunnel or disconnect laptop and verify the ESP32 retry/buffer behavior.
8. Restore connectivity and verify retry delivery does not duplicate records.
