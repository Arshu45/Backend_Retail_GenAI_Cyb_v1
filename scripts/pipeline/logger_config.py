#!/usr/bin/env python3
"""
Logging Configuration for Pipeline Scripts

Provides a centralized logging setup with:
- Console output: INFO level (minimal, important steps only)
- File output: DEBUG level (detailed execution information)
- Log files: logs/pipeline_YYYYMMDD_HHMMSS.log
"""

import logging
import os
from datetime import datetime
from pathlib import Path


def setup_logger(name: str, log_dir: str = "logs") -> logging.Logger:
    """
    Setup logger with console and file handlers.
    
    Args:
        name: Logger name (typically __name__ of the calling module)
        log_dir: Directory to store log files (default: "logs")
    
    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)  # Capture all levels
    
    # Avoid duplicate handlers if logger already configured
    if logger.handlers:
        return logger
    
    # Create logs directory if it doesn't exist
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)
    
    # Check if a log file path is already set (from parent process)
    log_file_path = os.environ.get('PIPELINE_LOG_FILE')
    
    if log_file_path:
        # Use existing log file from parent process
        log_file = Path(log_file_path)
    else:
        # Generate new timestamped log filename (for main process)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_path / f"pipeline_{timestamp}.log"
        # Set environment variable so child processes use the same file
        os.environ['PIPELINE_LOG_FILE'] = str(log_file)
    
    # Console handler - INFO level (minimal output)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter('%(message)s')
    console_handler.setFormatter(console_format)
    
    # File handler - DEBUG level (detailed output)
    file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')  # Append mode
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_format)
    
    # Add handlers to logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get or create a logger instance.
    
    Args:
        name: Logger name (typically __name__ of the calling module)
    
    Returns:
        Logger instance
    """
    return setup_logger(name)
