"""MAO Testing SDK exceptions."""


class MAOError(Exception):
    """Base exception for MAO Testing SDK."""
    pass


class TracingError(MAOError):
    """Error during tracing operations."""
    pass


class ConfigError(MAOError):
    """Configuration error."""
    pass


class ExportError(MAOError):
    """Error exporting trace data."""
    pass
