# logging_config.py
import logging
from logging.handlers import RotatingFileHandler
from typing import Optional

# Define the format string with placeholders
# - asctime: For date/time
# - filename: Source file name
# - lineno: Line number
# - funcName: Function name
# - threadName: Thread name
# - levelname: Log level (e.g., DEBUG, INFO)
# - message: The log message
default_fmt = '%(asctime)s.%(msecs)03d-%(filename)s:%(lineno)d-%(funcName)s()-%(threadName)s-%(levelname)s- %(message)s'
# Australian date format: DD-MM-YYYY HH:MM:SS (no milliseconds for simplicity)
# Example: 25-12-2023 14:30:59.123
date_fmt='%d-%m-%Y %H:%M:%S'

def setup_logger(name: str = 'default_app_logger', log_file: Optional[str] = '', console_level: int = logging.INFO, logfile_level: int = logging.DEBUG, max_bytes: int = 10485760, backup_count: int = 5) -> logging.Logger:
    """
    Sets up a logger with a file handler and a console handler.
    :param name: The name of the logger.
    :param log_file: The optional path to the log file.
    :param level: The logging level (e.g., logging.INFO, logging.DEBUG).
    :param max_bytes: The maximum size of the log file before rotation (in bytes).
    :param backup_count: The number of backup log files to keep.
    :return: A configured logger instance.
    """

    logger = logging.getLogger(name)
    logger.setLevel(console_level)

    #print(f'Configuring logger: {name} with handlers: {logger.handlers}')
    # Prevent adding multiple handlers if the logger is already configured
    if not logger.handlers:
        #print(f'Setting up logger: {name}, log_file: {log_file}, console_level: {console_level}, logfile_level: {logfile_level}, max_bytes: {max_bytes}, backup_count: {backup_count}')
        # Console handler for logging to the console
        console_handler = logging.StreamHandler()
        console_handler.setLevel(console_level)

        # Define log format
        formatter = logging.Formatter(fmt=default_fmt, datefmt=date_fmt)
        console_handler.setFormatter(formatter)

        # Add console handler to the logger
        logger.addHandler(console_handler)

        if log_file:
            #print (f'Adding file handler for log file: {log_file}')
            # File handler for logging to a file with rotation
            file_handler = RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count)
            file_handler.setLevel(logfile_level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

    return logger

# Example usage:
if __name__ == "__main__":
    logger = setup_logger('my_app', log_file='./logs/my_app.log', console_level=logging.DEBUG, logfile_level=logging.INFO)
    logger.debug('This is a debug message')
    logger.info('This is an info message')
    logger.warning('This is a warning message')
    logger.error('This is an error message')
    logger.critical('This is a critical message')