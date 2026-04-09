from pydantic import Field
from pydantic_settings import BaseSettings

DEFAULT_RATE_LIMITS: dict[str, int] = {
    "requests_per_minute": 1000,
    "requests_per_hour": 50000,
}

DEFAULT_CONSTRAINTS: dict[str, int] = {
    "max_batch_size": 1000,
    "max_message_length": 10000,
    "max_error_message_length": 5000,
    "max_stack_trace_length": 50000,
    "max_attributes_size_bytes": 102400,
    "max_environment_length": 20,
    "max_release_length": 100,
    "max_platform_version_length": 50,
    "max_error_type_length": 255,
}


class LedgerConfig(BaseSettings):

    base_url: str = Field(
        default="https://ledger-server.jtuta.cloud",
        description="Ledger server URL - single source of truth",
    )

    flush_interval: float = Field(
        default=5.0, gt=0, description="Interval in seconds between automatic buffer flushes"
    )

    flush_size: int = Field(
        default=100, gt=0, description="Number of logs that trigger an automatic flush"
    )

    max_buffer_size: int = Field(
        default=10000, gt=0, description="Maximum number of logs to keep in buffer"
    )

    http_timeout: float = Field(default=5.0, gt=0, description="HTTP request timeout in seconds")

    http_pool_size: int = Field(default=10, gt=0, description="HTTP connection pool size")

    rate_limit_buffer: float = Field(
        default=0.9, gt=0, le=1, description="Rate limit buffer percentage"
    )

    class Config:
        env_prefix = "LEDGER_"
        case_sensitive = False


DEFAULT_CONFIG = LedgerConfig()
