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

5. **Linter and Formatter**

   We use **RUFF** which is faster, less opinionated and more configurable than black.
   The ruff VSCode extension formats automatically on saving files. Get it here https://marketplace.visualstudio.com/items?itemName=charliermarsh.ruff

   The formatOnSave settings are persisted in `.vscode/settings.json`.

   INFO: The pipeline enforces this formatting and fails on mismatches.

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
   --build-arg BUILD_VERSION=0.9.2 \
   -t fiscalismia-webscraper:0.9.2 \
   "."
# nginx listens at port 5000
podman run \
   --env-file .env \
   --rm -it \
   -p 3003:3003 \
   --name fiscalismia-webscraper \
   fiscalismia-webscraper:0.9.2
```

## Python Pip and Podman locally behind Windows Netskope Proxy and Artifactory

INFO: Check code in private repository workbench_toolset