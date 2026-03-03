import uvicorn
from dotenv import load_dotenv

load_dotenv()  # loads .env from project root before app starts

if __name__ == "__main__":
  uvicorn.run(
    "api.main:fastapi", host="0.0.0.0", port=3003, reload=True, timeout_keep_alive=60, log_level="debug", loop="uvloop"
  )
