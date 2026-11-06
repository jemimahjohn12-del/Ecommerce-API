from fastapi import FastAPI

from app.presentation.routes import auth

app = FastAPI(title="E-Commerce & Order Management API")

app.include_router(auth.router)


@app.get("/", tags=["Health"])
def health():
    return {"status": "ok"}