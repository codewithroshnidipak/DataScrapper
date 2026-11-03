"""
Backward compatibility bridge for config.py -> settings.py
"""

from settings import (
    BASE_DIR,
    BASE_URL,
    SEARCH_URL,
    HEADLESS_MODE,
    REQUEST_DELAY_MIN,
    REQUEST_DELAY_MAX,
    PAGE_TIMEOUT,
    MAX_RETRIES,
    OUTPUT_DIR,
    EXCEL_FILENAME,
    CSV_FILENAME,
    EXCEL_OUTPUT_PATH as DEFAULT_EXCEL_OUTPUT,
    CSV_OUTPUT_PATH as DEFAULT_CSV_OUTPUT,
    LOG_LEVEL,
    LOG_FILE_PATH,
    USER_AGENT,
    PROXY_URL,
    DATA_COLUMNS,
    DEFAULT_LINKS
)
