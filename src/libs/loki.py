from python_loki_logger import LokiLogger

import logging

class LokiHandler(logging.Handler):
    def __init__(self, loki: LokiLogger, level=logging.NOTSET):
        super().__init__(level)
        self.loki_logger = loki
    
    def emit(self, record: logging.LogRecord):
        if record.levelno == logging.DEBUG:
            self.loki_logger.debug(record.getMessage())
        elif record.levelno == logging.INFO:
            self.loki_logger.info(record.getMessage())
        elif record.levelno == logging.WARNING:
            self.loki_logger.warning(record.getMessage())
        elif record.levelno == logging.ERROR:
            self.loki_logger.error(record.getMessage())