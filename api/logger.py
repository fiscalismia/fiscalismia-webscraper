import logging
import sys
import json
import json
from fastapi import HTTPException, status
from api.colors import tty_colors
from typing import Any
from datetime import datetime
from zoneinfo import ZoneInfo

# Add a success level between INFO and WARNING
logging.SUCCESS = 25
logging.addLevelName(logging.SUCCESS, "SUCCESS")


class DateTimeEncoder(json.JSONEncoder):
  """Custom JSON encoder that properly handles datetime objects.

  by default. This encoder converts them to ISO format strings.
  """

  def default(self, obj):
    if isinstance(obj, datetime):
      return obj.isoformat()
    return super().default(obj)


class CustomLogMessageFormatter(logging.Formatter):
  """Custom formatter that adds the log level and a timestamp to each log message."""

  def format(self, record):
    # First get the original formatted message
    message = super().format(record)
    # Get the log level name from the record
    level_name = record.levelname
    # Add timestamp in Berlin timezone
    timestamp = datetime.now(ZoneInfo("Europe/Berlin")).strftime("%Y-%m-%d %H:%M:%S")
    # Construct the final message with the desired format
    return f"{level_name} LOG - [{timestamp}]:\n{message}"


class ColoredLogger:
  """Minimal colored logging utility to replace print statements."""

  def __init__(self, name="fiscalismia-webscraper-logger"):
    self.logger = logging.getLogger(name)

    # Only configure once
    if not self.logger.handlers:
      self.logger.setLevel(logging.DEBUG)  # default

      # Console handler
      console = logging.StreamHandler(sys.stdout)
      console.setLevel(logging.DEBUG)  # default

      # Custom formatter with log level and timestamp
      formatter = CustomLogMessageFormatter("%(message)s")
      console.setFormatter(formatter)

      self.logger.addHandler(console)

  def _log(self, level: int, msg: Any, user_vkey: str | None = None):
    """Internal log handler for both console and CloudWatch."""
    self.logger.log(level, msg)

  def debug(self, msg: Any, user_vkey: str | None = None):
    """Log debug message with gray color"""
    self._log(logging.DEBUG, f"{tty_colors.DEBUG}{msg}{tty_colors.RESET}", user_vkey)

  def info(self, msg: Any, user_vkey: str | None = None):
    """Log info message with blue color"""
    self._log(logging.INFO, f"{tty_colors.INFO}{msg}{tty_colors.RESET}", user_vkey)

  def success(self, msg: Any, user_vkey: str | None = None):
    """Log success message with green color"""
    self._log(logging.SUCCESS, f"{tty_colors.SUCCESS}{msg}{tty_colors.RESET}", user_vkey)

  def warning(self, msg: Any, user_vkey: str | None = None):
    """Log warning message with yellow color"""
    self._log(logging.WARNING, f"{tty_colors.YELLOW}{msg}{tty_colors.RESET}", user_vkey)

  def error(self, msg: Any, user_vkey: str | None = None):
    """Log error message with red background"""
    self._log(logging.ERROR, f"{tty_colors.ERROR}{msg}{tty_colors.RESET}", user_vkey)

  def critical(self, msg: Any, user_vkey: str | None = None):
    """Log critical message with bright red color"""
    self._log(logging.CRITICAL, f"{tty_colors.CRITICAL}{msg}{tty_colors.RESET}", user_vkey)

  def header(self, msg: Any, level: int = 1, user_vkey: str | None = None):
    """Log header with specific styling based on level"""
    header_msg = ""
    if level == 1:
      header_msg = f"{tty_colors.HEADER_1}{msg}{tty_colors.RESET}"
    elif level == 2:
      header_msg = f"{tty_colors.HEADER_2}{msg}{tty_colors.RESET}"
    elif level == 3:
      header_msg = f"{tty_colors.HEADER_3}{msg}{tty_colors.RESET}"
    else:
      raise Exception("Add level parameters. Valid values: level=1 | level=2 | level=3 ")
    self._log(logging.INFO, header_msg, user_vkey)


# Create a singleton instance
logger = ColoredLogger()


# overwrite log level after instantiation
def set_global_log_level(level: int):
  """Set the log level for the entire application."""
  logger.logger.setLevel(level)
  for handler in logger.logger.handlers:
    handler.setLevel(level)
