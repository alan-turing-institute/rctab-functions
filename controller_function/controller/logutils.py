"""Utils to send logs to Azure Application Insights."""

import logging
import os
from functools import lru_cache

from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry.instrumentation.logging.handler import LoggingHandler
from opentelemetry.sdk.resources import SERVICE_NAME, Resource

from controller import settings

DEFAULT_SERVICE_NAME = "rctab-controller"


class CodeAttributesFilter(logging.Filter):
    """Add the source location of each log record.

    The module, function and line number are standard LogRecord fields, which
    the OpenTelemetry handler excludes from the attributes it exports unless it
    is built with log_code_attributes=True. configure_azure_monitor() does not
    build it that way, so add them here under their OpenTelemetry names. They
    appear as customDimensions in Application Insights, as they did under the
    previous OpenCensus handler.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Add the source location attributes to the current log record."""
        setattr(record, "code.file.path", record.pathname)
        setattr(record, "code.function.name", record.funcName)
        setattr(record, "code.line.number", record.lineno)

        return True


@lru_cache(maxsize=1)
def configure_telemetry(connection_string: str, logger_name: str) -> None:
    """Configure Azure Monitor once per process.

    configure_azure_monitor() sets up process-wide state, so it must not be
    called more than once. Live metrics and performance counters are disabled:
    both stream continuously, which suits a long-running web app rather than a
    timer-triggered function that wakes up, does its work and exits.

    Args:
        connection_string: The Application Insights connection string.
        logger_name: The logger to attach the handler to. Records from child
            loggers reach it by propagation.
    """
    service_name = os.environ.get("OTEL_SERVICE_NAME", DEFAULT_SERVICE_NAME)
    configure_azure_monitor(
        connection_string=connection_string,
        logger_name=logger_name,
        resource=Resource.create({SERVICE_NAME: service_name}),
        enable_live_metrics=False,
        enable_performance_counters=False,
    )

    # Filter the handler rather than the logger, so that records arriving by
    # propagation from child loggers are covered too.
    for handler in logging.getLogger(logger_name).handlers:
        if isinstance(handler, LoggingHandler):
            handler.addFilter(CodeAttributesFilter())


def add_log_handler_once(name: str = "controller") -> None:
    """Send logs from the named logger to Azure Application Insights.

    Telemetry is sent to the Application Insights instance associated with the
    connection string in settings. The logger name is recorded automatically as
    a custom dimension, so log messages can be filtered by it on Azure.

    Args:
        name: Name of the logger instance to which we add the log handler.
    """
    log_settings = settings.get_settings()
    connection_string = log_settings.APPLICATIONINSIGHTS_CONNECTION_STRING
    if connection_string:
        configure_telemetry(connection_string, name)
