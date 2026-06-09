# fiscalismia-webscraper
Playwright browser automation running on a remote VM, exposing live recording stream of the browser interaction via WebSocket API call -  the browser session is captures as jpeg screenshots of headless CDP browser sessions and sent as binary encoded packets to the client, rendering blobs into a canvas as ImageBitmaps. Webscraping targets are german supermarket chains, extracting food item discounts from their leaflets via alt-text extraction, OCR image parsing with subsequent ETL data pipelines sanitizing the data. The sanitized data is passed as unstructured text inputs to an LLM API Endpoint for transformation into a structured JSON payload for later database insertion via SQL generated in the main fiscalismia-backend.
The Python Backend is a very basic dockerized FastAPI server behind an nginx reverse-proxy, exposing routes protected via jwt authentication.

**Performance Tuning:**
- Uvicorn is configured with `--loop uvloop` (see `supervisord.conf` and `main.py`). uvloop is a drop-in replacement for Python's default asyncio event loop, provides 2-4x faster I/O scheduling, built on libuv (the same C library behind Node.js). Once installed via the `--loop` flag, it globally replaces the asyncio event loop for the entire process — all `asyncio.Queue`, `asyncio.wait_for`, `await` calls etc. run on uvloop automatically without code changes.
- TLS1.3 session ticket reuse for cached responses configured in `nginx.conf` with `ssl_session_tickets on;` and `ssl_session_timeout 4h;` - confirmed with test commands found below in this README

## Setup

**Dependencies**

- Python3.13+

**Installation**

1. **Navigate to the Project Folder:**

   ```bash
   cd ~/git/fiscalismia-webscraper
   ```

2. **Environment Variables:**

   Store the `.env` in the root folder of `fiscalismia-webscraper`. Ensure that you never upload this file to Git, as it contains sensitive information!
   ```bash
   JWT_SECRET=
   SNYK_TOKEN=
   ```

3. **Github Secrets:**

   Set up Github Secrets in your Repository Settings, for the pipeline to run successfully. These can and should be the same as in your `.env` file.
   ```bash
   JWT_SECRET
   SNYK_TOKEN
   ```

4. **Linter and Formatter**

   We use **RUFF** which is faster, less opinionated and more configurable than black.
   The ruff VSCode extension formats automatically on saving files. Get it here https://marketplace.visualstudio.com/items?itemName=charliermarsh.ruff

   The formatOnSave settings are persisted in `.vscode/settings.json`.

   INFO: The pipeline enforces this formatting and fails on mismatches.

5. **Dependency Resolution**

```bash
cd ~/git/fiscalismia-webscraper
python -m venv .venv
source .venv/bin/activate
pip install pip-tools
pip-compile --generate-hashes --strip-extras --output-file=requirements.txt pyproject.toml
pip install -r requirements.txt
```

## Running

**Locally Venv:**

```bash
   cd ~/git/fiscalismia-webscraper
   source .venv/bin/activate
   python main.py
   # send queries to http://localhost:3003/hc
```

**Locally Podman:**

```bash
# add only on landline wifi
# --no-cache \
# --pull \
podman build \
   --rm \
   -f "Dockerfile" \
   --build-arg BUILD_VERSION=0.9.3 \
   -t fiscalismia-webscraper:0.9.3 \
   "."
# nginx listens at port 5000
podman run \
   --env-file .env \
   --rm -it \
   -p 3003:3003 \
   --name fiscalismia-webscraper \
   fiscalismia-webscraper:0.9.3
```

## Updating Dependencies

```bash
cd ~/git/fiscalismia-webscraper
source .venv/bin/activate
pip install --upgrade pip
pip install pip-tools
pip-compile --upgrade --generate-hashes --strip-extras --output-file=requirements.txt pyproject.toml
```

## openssl TLS1.3 session caching for nginx performance

to test:
```bash
# Step 1: Connect and wait briefly for the post-handshake NewSessionTicket
(sleep 2; echo "Q") | openssl s_client -connect fastapi.demo.fiscalismia.com:443 \
   -tls1_3 -servername fastapi.demo.fiscalismia.com -sess_out /tmp/tls_session.pem 2>/dev/null
# Step 2: Resume with the saved ticket
echo "Q" | openssl s_client -connect fastapi.demo.fiscalismia.com:443 \
   -tls1_3 -servername fastapi.demo.fiscalismia.com -sess_in /tmp/tls_session.pem 2>&1 \
   | grep -E "^(New|Reused)"
# Expected: Reused, TLSv1.3, Cipher is TLS_AES_256_GCM_SHA384
```