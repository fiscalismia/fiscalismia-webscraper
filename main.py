import uvicorn
from dotenv import load_dotenv

load_dotenv()  # loads .env from project root before app starts

if __name__ == "__main__":
    uvicorn.run(
        "app.main:api",
        host="0.0.0.0",
        port=8000,
        reload=True,
        timeout_keep_alive=90,
        log_level="debug",
    )