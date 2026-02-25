# fiscalismia-webscraper
Playwright browser automation running on a remote VM, exposing live recording stream of the browser interaction via WebSocket API call.
Backend is a very basic dockerized FastAPI server exposing routes protected via jwt authentication.


## Setup

**Dependencies**

- Python3.13+

**Installation**

1. **Navigate to the Project Folder:**

   ```bash
   cd ~/git/fiscalismia-webscraper
   ```

2. **Setup Virtual Environment:**

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Environment Variables:**

   Store the `.env` in the root folder of `fiscalismia-webscraper`. Ensure that you never upload this file to Git, as it contains sensitive information!
   ```bash
   JWT_SECRET=
   SNYK_TOKEN=
   ```

4. **Github Secrets:**

   Set up Github Secrets in your Repository Settings, for the pipeline to run successfully. These can and should be the same as in your `.env` file.
   ```bash
   JWT_SECRET
   SNYK_TOKEN
   ```

## Running

**Locally Venv:**

```bash
   cd ~/git/fiscalismia-webscraper
   source .venv/bin/activate
   python main.py
   # send queries to http://localhost:8000/hc
```

**Locally Podman:**

```bash
podman build \
   --pull \
   --no-cache \
   --rm \
   -f "Dockerfile" \
   --build-arg BUILD_VERSION=0.9.1 \
   -t fiscalismia-webscraper:0.9.1 \
   "."
podman run \
   --env-file .env \
   --rm -it \
   -p 8000:8000 \
   --name fiscalismia-webscraper \
   fiscalismia-webscraper:0.9.1
```