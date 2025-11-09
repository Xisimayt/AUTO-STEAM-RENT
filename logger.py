import logging
import coloredlogs

# Create a logger
logger = logging.getLogger(__name__)

# Configure coloredlogs for console output
coloredlogs.install(
    level="DEBUG",
    logger=logger,
    fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Add a FileHandler to save logs to a file
file_handler = logging.FileHandler("application.log", encoding="utf-8")
file_handler.setLevel(logging.DEBUG)  # Set the logging level for the file
file_formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

logger.info("Логер запущен ✅")
