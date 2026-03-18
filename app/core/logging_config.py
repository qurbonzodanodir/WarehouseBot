import logging
import sys

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ]
    )
    # Reduce noise from aiogram and uvicorn
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.INFO)
