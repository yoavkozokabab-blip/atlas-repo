"""Safe Windows app discovery and launcher (Phase 15)."""

from apps.app_registry import AppRegistry
from apps.discovery import DiscoveredApp, discover_installed_apps
from apps.launcher import launch_app
from apps.safety import SafetyError, validate_launch_path

__all__ = [
    "AppRegistry",
    "DiscoveredApp",
    "SafetyError",
    "discover_installed_apps",
    "launch_app",
    "validate_launch_path",
]
