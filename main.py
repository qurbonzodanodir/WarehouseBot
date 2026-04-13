import uvicorn
from app.core.config import settings
from app.core.logging_config import setup_logging


def main() -> None:
    setup_logging()
    uvicorn.run(
        "app.api.app:app",
        host="0.0.0.0",
        port=8030,
        reload=False,
    )


if __name__ == "__main__":
    main()
