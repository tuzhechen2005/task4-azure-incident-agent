"""Local Uvicorn entry point."""

from app.api.app import create_app
from app.config import Settings
from app.logging_config import configure_logging

settings = Settings()
configure_logging(
    level=settings.log_level,
    secrets=[
        settings.llm_api_key.get_secret_value(),
        settings.azure_openai_api_key.get_secret_value(),
    ],
)
app = create_app(settings=settings)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
