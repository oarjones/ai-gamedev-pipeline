import logging
import sys
from pathlib import Path


def setup_logging(level: str = "INFO"):
    logs_dir = Path("logs")
    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    logging.basicConfig(
        level=getattr(logging, str(level).upper(), logging.INFO),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(str(logs_dir / 'gateway.log'), encoding='utf-8')
        ]
    )

