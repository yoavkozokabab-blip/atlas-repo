"""Tests for intent classification."""

from brain.intent_classifier import classify
from core.types import Intent


def test_hebrew_open_cursor():
    req = classify("פתח קרסור")
    assert req.intent == Intent.OPEN_CURSOR
    assert req.confidence >= 0.9


def test_hebrew_trading_dashboard():
    req = classify("פתח את הדאשבורד")
    assert req.intent == Intent.OPEN_TRADING_DASHBOARD


def test_hebrew_daily_loop():
    req = classify("תריץ לופ יומי")
    assert req.intent == Intent.RUN_LIVE_DAILY_LOOP


def test_hebrew_open_positions():
    req = classify("תראה פוזיציות פתוחות")
    assert req.intent == Intent.SHOW_OPEN_POSITIONS


def test_hebrew_system_status():
    req = classify("מה מצב המחשב")
    assert req.intent == Intent.SHOW_SYSTEM_STATUS


def test_english_dashboard():
    req = classify("open dashboard")
    assert req.intent == Intent.OPEN_TRADING_DASHBOARD


def test_hebrew_last_errors():
    req = classify("תראה שגיאות אחרונות")
    assert req.intent == Intent.SHOW_LAST_ERRORS


def test_hebrew_dashboard_health():
    req = classify("תראה מצב הדאשבורד")
    assert req.intent == Intent.SHOW_DASHBOARD_HEALTH


def test_find_risk_usage():
    req = classify("איפה מוגדר risk_per_trade")
    assert req.intent in (Intent.FIND_RISK_USAGE, Intent.FIND_CONFIG_KEY)


def test_unknown_command():
    req = classify("fly me to the moon")
    assert req.intent in (Intent.UNKNOWN, Intent.CLARIFY)
