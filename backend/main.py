from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes.lesson import router as lesson_router
from backend.api.routes.parse import router as parse_router
from backend.api.routes.review import router as review_router
from backend.core.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name, debug=settings.debug)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(parse_router)
app.include_router(lesson_router)
app.include_router(review_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
