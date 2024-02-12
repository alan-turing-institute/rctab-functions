"""Utils to send logs to Azure Application Insights."""
import logging
from typing import Optional

from opencensus.ext.azure.log_exporter import AzureLogHandler

from status import settings


class CustomDimensionsFilter(logging.Filter):
    """Add application-wide properties to AzureLogHandler records."""

    def __init__(self, custom_dimensions: Optional[dict] = None) -> None:
        """Add custom dimensions to the log record.

        Args:
            custom_dimensions: The custom dimensions to add to the log record.

        Returns:
            None
        """
        super().__init__()
        self.custom_dimensions = custom_dimensions or {}

    def filter(self, record: logging.LogRecord) -> bool:
        """Add the default custom_dimensions into the current log record.

        Args:
            record: The log record to which we add the custom dimensions.

        Returns:
            bool: True if the record was logged, False otherwise.
        """
        custom_dimensions = self.custom_dimensions.copy()
        custom_dimensions.update(getattr(record, "custom_dimensions", {}))
        record.custom_dimensions = custom_dimensions  # type: ignore

        return True


def add_log_handler_once(name: str = "status") -> None:
    """Add an Azure log handler to the logger with provided name.

    The log data is sent to the Azure Application Insights instance associated
    with the connection string in settings. Additional properties are added to
    log messages in form of a key-value pair which can be used to filter the log
    messages on Azure.

    Args:
        name: The name of the logger instance to which we add the log handler.
    """
    logger = logging.getLogger(name)
    log_settings = settings.get_settings()
    if log_settings.CENTRAL_LOGGING_CONNECTION_STRING:
        for handler in logger.handlers:
            # Only allow one AzureLogHandler per logger
            if isinstance(handler, AzureLogHandler):
                return

        custom_dimensions = {"logger_name": f"logger_{name}"}
        handler = AzureLogHandler(
            connection_string=log_settings.CENTRAL_LOGGING_CONNECTION_STRING
        )
        handler.addFilter(CustomDimensionsFilter(custom_dimensions))
        logger.addHandler(handler)
