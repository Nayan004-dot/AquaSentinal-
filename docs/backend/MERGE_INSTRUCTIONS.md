# Merge this backend package into the existing AquaSentinel repository

The ZIP intentionally contains only backend additions. It does not replace your current historical module, datasets, README, or other team work.

Assuming the repo is `~/Documents/AquaSentinel_GitHub_Starter` and the ZIP is in `~/Downloads`:

```bash
cd ~/Documents/AquaSentinel_GitHub_Starter
mkdir -p /tmp/aquasentinel-backend-package
unzip ~/Downloads/AquaSentinel_Backend_Implementation.zip -d /tmp/aquasentinel-backend-package
PACKAGE=/tmp/aquasentinel-backend-package/AquaSentinel_Backend_Implementation

# Add backend package and tests. Review first if either destination already exists.
cp -a "$PACKAGE/backend" ./backend
cp -a "$PACKAGE/tests/test_backend.py" ./tests/test_backend.py
cp "$PACKAGE/requirements-backend.txt" ./requirements-backend.txt
cp "$PACKAGE/.env.example" ./.env.example
mkdir -p docs/backend contracts
cp -a "$PACKAGE/docs/." ./docs/backend/
cp "$PACKAGE/contracts/outlet_sensor_telemetry.schema.json" ./contracts/
```

If `backend/` or `tests/test_backend.py` already exists, stop and inspect it before copying; do not overwrite existing work. Add the entries from `.gitignore.additions` to the repository's existing `.gitignore` only when those patterns are not already present. Do not replace the existing `.gitignore` wholesale.

Then install and test:

```bash
source .venv/bin/activate
pip install -r requirements-backend.txt
PYTHONPATH=. python -m pytest -q tests/test_backend.py
```

Run the service:

```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

In another terminal:

```bash
curl http://127.0.0.1:8000/api/v1/health
```

Before committing, inspect `git status -sb` and `git diff --check`. Never stage `.env`, the SQLite database, any Wi-Fi credentials, API tokens, or private SSH keys.
