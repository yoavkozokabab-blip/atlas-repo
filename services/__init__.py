"""Background services: autostart, health, watchdog."""

from services.autostart import (
    disable_autostart,
    enable_autostart,
    get_autostart_status,
)
from services.health import run_jarvis_health_check
from services.high_performance_runtime import (
    get_acceleration_profile,
    get_high_performance_runtime,
    submit_background,
)
from services.runtime_monitor import get_runtime_monitor, run_with_timeout
from services.observability import get_observability, structured_log

__all__ = [
    "enable_autostart",
    "disable_autostart",
    "get_autostart_status",
    "run_jarvis_health_check",
    "get_acceleration_profile",
    "get_high_performance_runtime",
    "submit_background",
    "get_runtime_monitor",
    "run_with_timeout",
    "get_observability",
    "structured_log",
]
