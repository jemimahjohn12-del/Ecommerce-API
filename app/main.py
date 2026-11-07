from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.domain import exceptions as errors
from app.presentation.routes import auth, categories, products

app = FastAPI(title="E-Commerce & Order Management API")

STATUS_BY_ERROR = {
    errors.NotFound: 404,
    errors.EmailAlreadyExists: 409,
    errors.SkuAlreadyExists: 409,
    errors.CategoryAlreadyExists: 409,
    errors.CategoryInUse: 409,
    errors.InvalidCredentials: 401,
    errors.PermissionDenied: 403,
    errors.InvalidData: 400,
}


@app.exception_handler(errors.DomainError)
async def domain_error_handler(request: Request, error: errors.DomainError):
    status_code = STATUS_BY_ERROR.get(type(error), 400)
    return JSONResponse(status_code=status_code, content={"detail": str(error)})


app.include_router(auth.router)
app.include_router(categories.router)
app.include_router(products.router)


@app.get("/", tags=["Health"])
def health():
    return {"status": "ok"}