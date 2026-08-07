import logging
import logging.handlers
from pathlib import Path


def configure_logging(level: int = logging.INFO, log_file: str = "logs/bot.log") -> None:
    """Call once, at process startup, before any other module logs.
    logging.basicConfig() is a no-op after the first call anywhere in the
    process, so scattering it across every module made the effective log
    format silently depend on import order.

    Everything goes to a rotating file only - the console is owned by the
    live dashboard (see src/dashboard.py), so a stray log line here would
    corrupt that display instead of helping anyone read it."""
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=5_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    logging.basicConfig(level=level, handlers=[handler])
