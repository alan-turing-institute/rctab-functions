"""Utils to send logs to Azure Application Insights."""

import logging
import os
from functools import lru_cache
from typing import Optional

from azure.monitor.opentelemetry.exporter import AzureMonitorLogExporter
from opentelemetry.instrumentation.logging.handler import LoggingHandler
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource

from controller import settings

DEFAULT_SERVICE_NAME = "rctab-controller"


class CustomDimensionsFilter(logging.Filter):
    """Add application-wide properties to log records."""

    def __init__(self, custom_dimensions: Optional[dict] = None) -> None:
        """Add custom dimensions, if provided, to the log record."""
        super().__init__()
        self.custom_dimensions = custom_dimensions or {}

    def filter(self, record: logging.LogRecord) -> bool:
        """Add the default custom dimensions to the current log record.

        Non-standard attributes on a LogRecord are exported as OpenTelemetry
        attributes, which appear as customDimensions in Application Insights.
        They are set individually rather than as a dict because OpenTelemetry
        attribute values must be primitives or homogeneous sequences.
        """
        for key, value in self.custom_dimensions.items():
            if not hasattr(record, key):
                setattr(record, key, value)

        return True


@lru_cache(maxsize=1)
def get_logger_provider(connection_string: str) -> LoggerProvider:
    """Build the process-wide logger provider.

    One provider, and therefore one batching background thread, is shared by
    every logger we attach a handler to.

    Args:
        connection_string: The Application Insights connection string.

    Returns:
        The logger provider, created on first call and reused afterwards.
    """
    service_name = os.environ.get("OTEL_SERVICE_NAME", DEFAULT_SERVICE_NAME)
    provider = LoggerProvider(resource=Resource.create({SERVICE_NAME: service_name}))
    provider.add_log_record_processor(
        BatchLogRecordProcessor(
            AzureMonitorLogExporter(connection_string=connection_string)
        )
    )

    return provider


def add_log_handler_once(name: str = "controller") -> None:
    """Add an Azure log handler to the logger with provided name.

    The log data is sent to the Azure Application Insights instance associated
    with the connection string in settings. Additional properties are added
    to log messages in form of a key-value pair which can be used to filter the
    log messages on Azure.

    Args:
        name: Name of the logger instance to which we add the log handler.
    """
    logger = logging.getLogger(name)
    log_settings = settings.get_settings()
    connection_string = log_settings.APPLICATIONINSIGHTS_CONNECTION_STRING
    if connection_string:
        for handler in logger.handlers:
            # Only allow one LoggingHandler per logger, since each additional
            # handler would export every record again.
            if isinstance(handler, LoggingHandler):
                return

        custom_dimensions = {"logger_name": f"logger_{name}"}
        handler = LoggingHandler(
            logger_provider=get_logger_provider(connection_string),
            # Export the module, function and line number, which the previous
            # OpenCensus handler surfaced as customDimensions.
            log_code_attributes=True,
        )
        handler.addFilter(CustomDimensionsFilter(custom_dimensions))
        logger.addHandler(handler)
