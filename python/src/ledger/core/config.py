from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_CONSTRAINTS: dict[str, int] = {
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
        default=5.0, gt=0, description="Interval in seconds between automatic batch exports"
    )

    flush_size: int = Field(
        default=100, gt=0, description="Number of records that trigger an automatic export"
    )

    max_buffer_size: int = Field(
        default=10000, gt=0, description="Maximum number of records to queue before export"
    )

    http_timeout: float = Field(default=5.0, gt=0, description="OTLP export timeout in seconds")

    tracing_enabled: bool = Field(default=True, description="Enable distributed tracing")

    trace_sample_rate: float = Field(
        default=0.1, ge=0.0, le=1.0, description="Head sample rate for tracing (0.0 to 1.0)"
    )

    metrics_export_interval: float = Field(
        default=60.0,
        gt=0,
        description="Interval in seconds between automatic metric exports (OTel default is 60s)",
    )

    service_name: str = Field(default="python", description="Service name attached to all spans")

    model_config = SettingsConfigDict(env_prefix="LEDGER_", case_sensitive=False)


DEFAULT_CONFIG = LedgerConfig()
