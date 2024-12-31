from app.main import app
import os

port = int(os.getenv("PORT", 10000))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
