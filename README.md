# fiscalismia-webscraper
Playwright browser automation running on a remote VM, exposing live recording stream of the browser interaction via WebSocket API call



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
   python main.py
   ```

3. **Environment Variables:**

   Store the `.env` in the root folder of `fiscalismia-webscraper`. Ensure that you never upload this file to Git, as it contains sensitive information!
   ```bash
   JWT_ENCODING_SECRET=
   SNYK_TOKEN=
   ```

4. **Github Secrets:**

   Set up Github Secrets in your Repository Settings, for the pipeline to run successfully. These can and should be the same as in your `.env` file.
   ```bash
   JWT_ENCODING_SECRET
   SNYK_TOKEN
   ```


## Developing

```
