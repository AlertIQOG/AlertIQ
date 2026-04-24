import logging
import sys


def setup_logging(debug: bool = False) -> None:
    """Configure application-wide logging."""
    log_level = logging.DEBUG if debug else logging.INFO

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )

    # Quiet down noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


# Module-level logger — import this in other modules:
# from app.core.logging import logger
logger = logging.getLogger("alertiq")
