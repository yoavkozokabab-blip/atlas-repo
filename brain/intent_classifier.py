"""Rule-based intent classifier (Hebrew + English)."""

from __future__ import annotations

import re
import unicodedata

from config import (
    CONFIDENCE_THRESHOLD,
    LLM_CLASSIFIER_ENABLED,
    LLM_FALLBACK_TO_RULES,
)
from core.types import CommandRequest, Intent

# (phrases, intent, confidence)
_PHRASE_RULES: list[tuple[list[str], Intent, float]] = [
    # Memory (Phase 6 + Phase 34 knowledge base)
    (["remember this"], Intent.REMEMBER_THIS, 0.94),
    (
        ["זכור שאני מעדיף", "remember preference", "remember that i prefer"],
        Intent.REMEMBER_PREFERENCE,
        0.92,
    ),
    (
        ["זכור שהפרויקט", "זכור שכאשר", "remember that", "זכור ש"],
        Intent.REMEMBER_FACT,
        0.88,
    ),
    (
        ["תראה מה אתה זוכר", "מה אתה זוכר", "show memory"],
        Intent.SHOW_MEMORY,
        0.91,
    ),
    (["list memory"], Intent.LIST_MEMORY, 0.90),
    (["show memory debug"], Intent.SHOW_MEMORY_DEBUG, 0.92),
    (
        ["what do you remember about", "מה אתה זוכר על"],
        Intent.SEARCH_MEMORY,
        0.92,
    ),
    (["חפש בזיכרון", "search memory"], Intent.SEARCH_MEMORY, 0.90),
    (
        ["summarize my day", "what needs my attention today", "find calendar conflicts"],
        Intent.SUMMARIZE_MY_DAY,
        0.92,
    ),
    (["summarize my last 100 emails"], Intent.SUMMARIZE_MY_LAST_100_EMAILS, 0.93),
    (
        ["what needs my attention today"],
        Intent.WHAT_NEEDS_MY_ATTENTION_TODAY,
        0.93,
    ),
    (["find calendar conflicts"], Intent.FIND_CALENDAR_CONFLICTS, 0.93),
    (["show browser debug"], Intent.SHOW_BROWSER_DEBUG, 0.92),
    (["open browser"], Intent.OPEN_BROWSER, 0.92),
    (["test real browser"], Intent.TEST_REAL_BROWSER, 0.92),
    (["test real voice conversation", "test real voice"], Intent.TEST_REAL_VOICE_CONVERSATION, 0.92),
    (["show desktop vision health", "desktop vision health"], Intent.SHOW_DESKTOP_VISION_HEALTH, 0.9),
    (["alpha setup check", "run alpha setup"], Intent.ALPHA_SETUP_CHECK, 0.92),
    (["show alpha report", "alpha report"], Intent.SHOW_ALPHA_REPORT, 0.9),
    (["show runtime config mismatches"], Intent.SHOW_RUNTIME_CONFIG_MISMATCHES, 0.92),
    (["show capability health"], Intent.SHOW_CAPABILITY_HEALTH, 0.92),
    (["show voice health"], Intent.SHOW_VOICE_HEALTH, 0.92),
    (["repair memory store"], Intent.REPAIR_MEMORY_STORE, 0.92),
    (["show browser health"], Intent.SHOW_BROWSER_HEALTH, 0.92),
    (["show desktop operator health"], Intent.SHOW_DESKTOP_OPERATOR_HEALTH, 0.92),
    (["show system health"], Intent.SHOW_SYSTEM_HEALTH, 0.92),
    (["show performance report"], Intent.SHOW_PERFORMANCE_REPORT, 0.92),
    (["summarize my inbox"], Intent.SUMMARIZE_MY_INBOX, 0.92),
    (["show urgent emails"], Intent.SHOW_URGENT_EMAILS, 0.92),
    (["summarize my calendar"], Intent.SUMMARIZE_MY_CALENDAR, 0.92),
    (["what is on my screen"], Intent.WHAT_IS_ON_MY_SCREEN, 0.93),
    (["summarize this screen"], Intent.SUMMARIZE_THIS_SCREEN, 0.93),
    (["click the button that says"], Intent.CLICK_BUTTON_THAT_SAYS, 0.92),
    (["type this"], Intent.TYPE_THIS, 0.92),
    (["switch to chrome"], Intent.SWITCH_TO_CHROME, 0.92),
    (["list open windows"], Intent.LIST_OPEN_WINDOWS, 0.92),
    (["search web for"], Intent.SEARCH_WEB_FOR, 0.92),
    (["find information about"], Intent.FIND_INFORMATION_ABOUT, 0.92),
    (["open the best result"], Intent.OPEN_BEST_RESULT, 0.92),
    (["summarize the top results"], Intent.SUMMARIZE_TOP_RESULTS, 0.92),
    (["compare these search results"], Intent.COMPARE_THESE_SEARCH_RESULTS, 0.92),
    (["extract key facts from this page"], Intent.EXTRACT_KEY_FACTS_FROM_THIS_PAGE, 0.92),
    (["save browser research report"], Intent.SAVE_BROWSER_RESEARCH_REPORT, 0.92),
    (["summarize this page"], Intent.SUMMARIZE_THIS_PAGE, 0.92),
    (["summarize current page"], Intent.SUMMARIZE_THIS_PAGE, 0.92),
    (["compare these results"], Intent.COMPARE_THESE_RESULTS, 0.92),
    (["compare these pages"], Intent.COMPARE_THESE_PAGES, 0.92),
    (["what tab is active"], Intent.WHAT_TAB_IS_ACTIVE, 0.92),
    (["what page am i on"], Intent.WHAT_TAB_IS_ACTIVE, 0.92),
    (["index project", "reindex project"], Intent.INDEX_PROJECT, 0.91),
    (
        ["search project knowledge", "find in project knowledge"],
        Intent.SEARCH_PROJECT_KNOWLEDGE,
        0.90,
    ),
    (["index project", "reindex project"], Intent.INDEX_PROJECT, 0.91),
    (
        ["search project knowledge", "search project", "find in project knowledge"],
        Intent.SEARCH_PROJECT_KNOWLEDGE,
        0.90,
    ),
    (["שכח alias", "delete alias", "מחק alias"], Intent.DELETE_ALIAS, 0.90),
    (["תראה aliases", "list aliases", "רשימת aliases"], Intent.LIST_ALIASES, 0.90),
    (
        ["קבע alias", "set alias", "זכור שכאשר אני אומר"],
        Intent.SET_ALIAS,
        0.88,
    ),
    (["שכח את זה", "שכח", "forget memory", "forget that"], Intent.FORGET_MEMORY, 0.85),
    (["list preferences", "רשימת העדפות"], Intent.LIST_PREFERENCES, 0.88),
    (["שכח העדפה", "forget preference"], Intent.FORGET_PREFERENCE, 0.88),
    # Assistant / capabilities (Phase 5)
    (
        [
            "מה אתה יודע לעשות",
            "איזה יכולות יש לך",
            "מה אתה יכול",
            "show capabilities",
            "what can you do",
            "תראה פקודות",
            "תן דוגמאות לפקודות",
        ],
        Intent.SHOW_CAPABILITIES,
        0.93,
    ),
    (["list skills", "רשימת סקילים", "list_skills"], Intent.LIST_SKILLS, 0.90),
    (
        [
            "תסביר סקיל",
            "explain skill",
            "תסביר את היכולת",
            "איזה פקודות מסחר יש",
        ],
        Intent.EXPLAIN_SKILL,
        0.90,
    ),
    (
        [
            "תן עזרה על",
            "help for",
            "help run",
            "איך אני מריץ",
            "עזרה על לופ",
        ],
        Intent.HELP_FOR_COMMAND,
        0.88,
    ),
    # Computer control (Phase 12 — predefined UI, disabled by default)
    (
        ["איזה אפליקציה בפוקוס", "get focused app", "focused app"],
        Intent.GET_FOCUSED_APP,
        0.94,
    ),
    (
        ["תראה חלונות מפורט", "list windows detailed", "detailed windows"],
        Intent.LIST_WINDOWS_DETAILED,
        0.93,
    ),
    (
        ["מה יש בקליפבורד", "get clipboard summary", "clipboard summary"],
        Intent.GET_CLIPBOARD_SUMMARY,
        0.93,
    ),
    (
        ["תעביר פוקוס לכרום", "focus window chrome", "focus chrome"],
        Intent.FOCUS_WINDOW,
        0.92,
    ),
    (
        ["נקה קליפבורד", "clear clipboard"],
        Intent.CLEAR_CLIPBOARD,
        0.92,
    ),
    (
        ["מזער חלון", "minimize window"],
        Intent.MINIMIZE_WINDOW,
        0.90,
    ),
    (
        ["הגדל חלון", "maximize window"],
        Intent.MAXIMIZE_WINDOW,
        0.90,
    ),
    # Services (Phase 11 — autostart, health, watchdog)
    (
        ["תפעיל הפעלה אוטומטית", "enable autostart", "enable startup"],
        Intent.ENABLE_AUTOSTART,
        0.94,
    ),
    (
        ["תבטל הפעלה אוטומטית", "disable autostart", "disable startup"],
        Intent.DISABLE_AUTOSTART,
        0.94,
    ),
    (
        ["מצב הפעלה אוטומטית", "show autostart status", "autostart status"],
        Intent.SHOW_AUTOSTART_STATUS,
        0.93,
    ),
    (
        ["בדוק את ג'רוויס", "בדוק את ג׳רוויס", "run jarvis health check", "check jarvis health"],
        Intent.RUN_JARVIS_HEALTH_CHECK,
        0.93,
    ),
    (
        ["מה מצב watchdog", "show watchdog status", "watchdog status"],
        Intent.SHOW_WATCHDOG_STATUS,
        0.92,
    ),
    # Workflows (Phase 10 — predefined sequences)
    (
        ["תראה workflows", "list workflows", "רשימת workflows"],
        Intent.LIST_WORKFLOWS,
        0.93,
    ),
    (
        ["תריץ בדיקת מערכת מסחר", "run workflow trading_health_check", "trading health check workflow"],
        Intent.RUN_WORKFLOW,
        0.94,
    ),
    (
        ["בדוק שגיאות במסך", "run workflow screen_error_check", "screen error check workflow"],
        Intent.RUN_WORKFLOW,
        0.93,
    ),
    (
        ["תסביר workflow מסחר", "explain workflow trading_health_check", "explain trading workflow"],
        Intent.EXPLAIN_WORKFLOW,
        0.92,
    ),
    # Diagnostics (Phase 9 — read-only cross-source)
    (
        ["הרץ אבחון", "run diagnostics", "full diagnostics"],
        Intent.RUN_DIAGNOSTICS,
        0.94,
    ),
    (
        ["אבחן דאשבורד", "diagnose dashboard", "dashboard diagnostics"],
        Intent.DIAGNOSE_DASHBOARD,
        0.93,
    ),
    (
        ["אבחן לופ מסחר", "diagnose trading loop", "trading loop diagnostics"],
        Intent.DIAGNOSE_TRADING_LOOP,
        0.92,
    ),
    (
        ["אבחן שגיאות אחרונות", "diagnose recent errors", "recent error diagnostics"],
        Intent.DIAGNOSE_RECENT_ERRORS,
        0.92,
    ),
    (
        ["נתח מסך נוכחי", "analyze current screen", "analyze screen"],
        Intent.ANALYZE_CURRENT_SCREEN,
        0.91,
    ),
    (
        ["הסבר כשלון אחרון", "explain last failure", "why did it fail"],
        Intent.EXPLAIN_LAST_FAILURE,
        0.91,
    ),
    (
        ["מה הצעדים הבאים", "suggest next steps", "next steps"],
        Intent.SUGGEST_NEXT_STEPS,
        0.90,
    ),
    # Phase 40 — operating assistant (read-only)
    (
        [
            "what am i doing",
            "what are you seeing",
            "current workspace",
            "מה אני עושה",
        ],
        Intent.WHAT_AM_I_DOING,
        0.93,
    ),
    (["review latest patch", "latest patch"], Intent.REVIEW_LATEST_PATCH, 0.92),
    (
        ["summarize recent changes", "recent git changes", "git summary"],
        Intent.SUMMARIZE_RECENT_CHANGES,
        0.91,
    ),
    (["show failing tests", "failing tests", "pytest status"], Intent.SHOW_FAILING_TESTS, 0.91),
    (
        ["summarize this file", "summarize file"],
        Intent.SUMMARIZE_THIS_FILE,
        0.90,
    ),
    (["show recent commands", "recent commands"], Intent.SHOW_RECENT_COMMANDS, 0.90),
    (
        [
            "explain this error",
            "explain what failed",
            "explain failure",
        ],
        Intent.EXPLAIN_THIS_ERROR,
        0.91,
    ),
    (["start study mode", "study mode"], Intent.START_STUDY_MODE, 0.92),
    (["focus mode", "enter focus"], Intent.FOCUS_MODE, 0.91),
    (["summarize my notes", "my study notes"], Intent.SUMMARIZE_MY_NOTES, 0.90),
    (["explain this code", "explain code"], Intent.EXPLAIN_THIS_CODE, 0.90),
    (["quiz me", "quiz"], Intent.QUIZ_ME, 0.89),
    (
        ["what should i study next", "study next"],
        Intent.WHAT_SHOULD_I_STUDY_NEXT,
        0.89,
    ),
    (
        [
            "explain this architecture",
            "summarize this module",
            "assistant explain",
        ],
        Intent.ASSISTANT_EXPLAIN,
        0.90,
    ),
    (
        [
            "make a plan",
            "plan a dashboard redesign",
            "assistant plan",
        ],
        Intent.ASSISTANT_PLAN,
        0.89,
    ),
    (
        ["what were we doing", "where were we", "continue session"],
        Intent.WHAT_WERE_WE_DOING,
        0.92,
    ),
    (["summarize session", "session summary"], Intent.SUMMARIZE_SESSION, 0.91),
    # Vision (Phase 8 / Phase 35 — read-only screen understanding)
    (
        [
            "מה יש במסך",
            "תראה מה מופיע במסך",
            "describe screen",
            "what is on screen",
        ],
        Intent.DESCRIBE_SCREEN,
        0.94,
    ),
    (
        [
            "קרא את הטקסט במסך",
            "read screen text",
            "read screen",
            "read what is on screen",
        ],
        Intent.READ_SCREEN_TEXT,
        0.94,
    ),
    (
        ["analyze active window", "analyze this window", "נתח חלון פעיל"],
        Intent.ANALYZE_ACTIVE_WINDOW,
        0.94,
    ),
    (
        ["find on screen", "find this on screen", "חפש במסך"],
        Intent.FIND_ON_SCREEN,
        0.93,
    ),
    (
        ["יש שגיאה במסך", "detect screen errors", "screen errors on display"],
        Intent.DETECT_SCREEN_ERRORS,
        0.93,
    ),
    (
        ["איזה חלון פתוח", "get active window", "active window"],
        Intent.GET_ACTIVE_WINDOW,
        0.93,
    ),
    (["צלם מסך", "take screenshot", "screenshot screen"], Intent.TAKE_SCREENSHOT, 0.92),
    (
        ["תראה חלונות פתוחים", "list visible windows", "list windows"],
        Intent.LIST_VISIBLE_WINDOWS,
        0.91,
    ),
    # Apps
    (["פתח קרסור", "פתחי קרסור", "open cursor"], Intent.OPEN_CURSOR, 0.95),
    (["פתח כרום", "open chrome"], Intent.OPEN_CHROME, 0.95),
    (["פתח טרמינל", "פתח טרמינל", "open terminal"], Intent.OPEN_TERMINAL, 0.93),
    (
        ["פתח את התיקייה של הפרויקט", "פתח תיקיית פרויקט", "open project folder"],
        Intent.OPEN_PROJECT_FOLDER,
        0.92,
    ),
    (
        ["פתח לוג אחרון", "פתח את הלוג האחרון", "open latest log"],
        Intent.OPEN_LATEST_LOG,
        0.90,
    ),
    # Dashboard / loops
    (
        [
            "פתח את הדאשבורד",
            "פתח דאשבורד",
            "open dashboard",
            "open the dashboard",
            "open trading dashboard",
        ],
        Intent.OPEN_TRADING_DASHBOARD,
        0.95,
    ),
    (
        ["פתח כתובת דאשבורד", "open dashboard url"],
        Intent.OPEN_TRADING_DASHBOARD_URL,
        0.96,
    ),
    (
        ["תראה מצב הדאשבורד", "בדוק אם הדאשבורד חי", "show dashboard health", "dashboard health"],
        Intent.SHOW_DASHBOARD_HEALTH,
        0.93,
    ),
    (
        ["תריץ לופ יומי", "הרץ לופ יומי", "run live daily loop", "run daily loop"],
        Intent.RUN_LIVE_DAILY_LOOP,
        0.92,
    ),
    (
        ["תריץ לופ שבועי", "run live weekly loop", "weekly loop"],
        Intent.RUN_LIVE_WEEKLY_LOOP,
        0.90,
    ),
    # Safe app launcher (Phase 15)
    (
        ["find apps", "discover apps", "scan apps", "חפש אפליקציות"],
        Intent.DISCOVER_APPS,
        0.93,
    ),
    (
        ["list apps", "show apps", "תראה אפליקציות", "רשימת אפליקציות"],
        Intent.LIST_APPS,
        0.93,
    ),
    (
        ["פתח דיסקורד", "open discord"],
        Intent.OPEN_APP,
        0.94,
    ),
    (
        ["פתח ספוטיפיי", "open spotify", "launch spotify"],
        Intent.OPEN_APP,
        0.94,
    ),
    (
        ["פתח סטים", "open steam", "start steam", "launch steam"],
        Intent.OPEN_APP,
        0.94,
    ),
    # Safe website launcher (Phase 16)
    (
        ["list websites", "show websites", "רשימת אתרים"],
        Intent.LIST_WEBSITES,
        0.93,
    ),
    (
        ["open chatgpt", "open chat gpt", "פתח צאט גיפיטי"],
        Intent.OPEN_WEBSITE,
        0.94,
    ),
    (
        ["open tradingview", "open trading view", "פתח טריידינגויו"],
        Intent.OPEN_WEBSITE,
        0.94,
    ),
    (
        ["open youtube", "פתח יוטיוב"],
        Intent.OPEN_WEBSITE,
        0.94,
    ),
    (
        ["open gmail", "פתח גימייל"],
        Intent.OPEN_WEBSITE,
        0.94,
    ),
    (
        ["open github", "פתח גיטהאב"],
        Intent.OPEN_WEBSITE,
        0.94,
    ),
    (
        ["open google"],
        Intent.OPEN_WEBSITE,
        0.93,
    ),
    (
        ["open openai"],
        Intent.OPEN_WEBSITE,
        0.93,
    ),
    (
        ["open yohananof", "פתח יוחננוף"],
        Intent.OPEN_WEBSITE,
        0.93,
    ),
    # Trading read-only
    (
        ["תראה פוזיציות פתוחות", "show open positions", "open positions"],
        Intent.SHOW_OPEN_POSITIONS,
        0.92,
    ),
    (
        ["דוח אחרון", "latest report", "show latest report"],
        Intent.SHOW_LATEST_LIVE_REPORT,
        0.90,
    ),
    (
        ["תראה שגיאות אחרונות", "שגיאות אחרונות", "show last errors", "last errors"],
        Intent.SHOW_LAST_ERRORS,
        0.92,
    ),
    (
        ["תסכם את הלוג האחרון", "summarize latest log", "summarize log"],
        Intent.SUMMARIZE_LATEST_LOG,
        0.91,
    ),
    (
        ["תראה למה טריידים נדחו", "rejection reasons", "show rejection reasons"],
        Intent.SHOW_REJECTION_REASONS,
        0.90,
    ),
    (
        ["תראה טריידים חסומים", "blocked trades", "show blocked trades"],
        Intent.SHOW_BLOCKED_TRADES,
        0.90,
    ),
    (
        ["היסטוריית מסחר", "recent trading history", "trading history"],
        Intent.SHOW_RECENT_TRADING_HISTORY,
        0.88,
    ),
    # Code intelligence
    (
        ["חפש קובץ", "search file", "search project file"],
        Intent.SEARCH_PROJECT_FILE_BY_NAME,
        0.88,
    ),
    (["חפש בקוד", "search code", "search in code"], Intent.SEARCH_CODE_TEXT, 0.88),
    (["חפש פונקציה", "find function"], Intent.FIND_FUNCTION, 0.88),
    (["חפש מחלקה", "find class"], Intent.FIND_CLASS, 0.88),
    (
        ["איפה מוגדר risk_per_trade", "find risk usage", "find risk"],
        Intent.FIND_RISK_USAGE,
        0.90,
    ),
    (
        ["איפה הלוגיקה של delayed entry", "find delayed entry", "delayed entry logic"],
        Intent.FIND_DELAYED_ENTRY_LOGIC,
        0.90,
    ),
    (
        ["איפה יש execution events", "find execution events", "execution events logic"],
        Intent.FIND_EXECUTION_EVENTS_LOGIC,
        0.90,
    ),
    # Voice / STT
    (
        [
            "show stt status",
            "stt status",
            "speech status",
            "מצב תמלול",
            "הגדרות תמלול",
            "הצג סטטוס תמלול",
        ],
        Intent.SHOW_STT_STATUS,
        0.93,
    ),
    (
        [
            "benchmark stt",
            "stt benchmark",
            "benchmark speech",
        ],
        Intent.BENCHMARK_STT,
        0.92,
    ),
    (
        [
            "list stt engines",
            "list speech engines",
            "show stt engines",
        ],
        Intent.LIST_STT_ENGINES,
        0.92,
    ),
    (
        [
            "show stt stack status",
            "stt stack status",
            "speech stack status",
        ],
        Intent.SHOW_STT_STACK_STATUS,
        0.94,
    ),
    (
        [
            "auto tune voice",
            "auto tune",
            "tune voice settings",
        ],
        Intent.AUTO_TUNE_VOICE,
        0.92,
    ),
    (
        [
            "apply auto tune voice",
            "apply auto tune",
        ],
        Intent.AUTO_TUNE_VOICE,
        0.91,
    ),
    (
        [
            "test direct speech",
            "direct speech test",
            "test jarvis audio",
        ],
        Intent.TEST_DIRECT_SPEECH,
        0.93,
    ),
    (
        [
            "test normal speech path",
            "normal speech path test",
            "test normal speech",
        ],
        Intent.TEST_NORMAL_SPEECH,
        0.93,
    ),
    (
        [
            "audio route prove",
            "prove audio route",
            "audio route test",
        ],
        Intent.AUDIO_ROUTE_PROVE,
        0.94,
    ),
    (
        [
            "force direct pyttsx3 normal mode",
            "force direct pyttsx3",
            "force direct normal mode",
        ],
        Intent.FORCE_DIRECT_PYTTSX3_NORMAL_MODE,
        0.94,
    ),
    (
        [
            "test subprocess speech",
            "subprocess speech test",
        ],
        Intent.TEST_SUBPROCESS_SPEECH,
        0.94,
    ),
    (
        [
            "force shell tts test",
            "shell tts test",
            "run shell tts test",
        ],
        Intent.FORCE_SHELL_TTS_TEST,
        0.94,
    ),
    (
        [
            "voice smoke test",
            "run voice smoke test",
            "voice smoke",
        ],
        Intent.VOICE_SMOKE_TEST,
        0.93,
    ),
    (
        [
            "foundation health check",
            "run foundation health check",
            "jarvis health check",
        ],
        Intent.FOUNDATION_HEALTH_CHECK,
        0.94,
    ),
    (
        ["show launcher status", "launcher status"],
        Intent.SHOW_LAUNCHER_STATUS,
        0.93,
    ),
    (
        [
            "show runtime threads",
            "runtime threads",
            "show threads",
        ],
        Intent.SHOW_RUNTIME_THREADS,
        0.93,
    ),
    (
        ["show control status", "control status"],
        Intent.SHOW_CONTROL_STATUS,
        0.93,
    ),
    (
        ["show screen status", "screen status"],
        Intent.SHOW_SCREEN_STATUS,
        0.93,
    ),
    (
        ["benchmark voice modes", "voice mode benchmark"],
        Intent.BENCHMARK_VOICE_MODES,
        0.92,
    ),
    (
        [
            "show tts threads",
            "tts threads",
            "show speech threads",
        ],
        Intent.SHOW_TTS_THREADS,
        0.92,
    ),
    (
        [
            "show tts status",
            "tts status",
            "voice output status",
            "speech output status",
        ],
        Intent.SHOW_TTS_STATUS,
        0.93,
    ),
    (
        ["show tts debug", "tts debug", "tts output debug"],
        Intent.SHOW_TTS_DEBUG,
        0.93,
    ),
    (
        ["test tts playback", "tts playback test", "playback test"],
        Intent.TEST_TTS_PLAYBACK,
        0.93,
    ),
    (
        ["test direct tts", "direct tts test"],
        Intent.TEST_DIRECT_TTS,
        0.96,
    ),
    (
        ["test streaming stt", "streaming stt test"],
        Intent.TEST_STREAMING_STT,
        0.93,
    ),
    (
        ["list voices", "list tts voices", "show voices"],
        Intent.LIST_VOICES,
        0.93,
    ),
    (
        ["switch voice", "change voice", "switch tts engine"],
        Intent.SWITCH_VOICE,
        0.92,
    ),
    (
        ["set female voice", "female voice", "use female voice"],
        Intent.SET_FEMALE_VOICE,
        0.93,
    ),
    (
        ["set cinematic voice", "cinematic voice", "iron man voice"],
        Intent.SET_CINEMATIC_VOICE,
        0.92,
    ),
    (
        [
            "set voice emotion calm",
            "voice emotion assistant",
            "voice emotion alert",
            "voice emotion focused",
            "voice emotion cinematic",
            "set calm voice",
            "set alert voice",
        ],
        Intent.SET_VOICE_EMOTION,
        0.90,
    ),
    (
        ["benchmark tts", "tts benchmark", "voice benchmark"],
        Intent.BENCHMARK_TTS,
        0.91,
    ),
    (
        ["stop speaking", "stop speech", "interrupt speech", "barge in"],
        Intent.STOP_SPEAKING,
        0.92,
    ),
    (
        ["stop speech hard", "kill speech", "kill tts", "force stop speech"],
        Intent.STOP_SPEECH_HARD,
        0.95,
    ),
    (
        [
            "show voice debug",
            "voice debug",
            "speech debug",
            "voice diagnostics",
        ],
        Intent.SHOW_VOICE_DEBUG,
        0.94,
    ),
    (
        [
            "show audio status",
            "audio status",
            "playback status",
            "speaker status",
        ],
        Intent.SHOW_AUDIO_STATUS,
        0.94,
    ),
    (
        [
            "test voice output",
            "test voice",
            "test audio",
            "test speech",
            "say test phrase",
            "try speaking",
            "say something",
        ],
        Intent.TEST_VOICE_OUTPUT,
        0.94,
    ),
    (
        ["show wake diagnostics", "wake diagnostics", "wake session diagnostics"],
        Intent.SHOW_WAKE_DIAGNOSTICS,
        0.94,
    ),
    (
        ["show audio devices", "list audio devices", "audio devices"],
        Intent.SHOW_AUDIO_DEVICES,
        0.94,
    ),
    (
        ["tool mode status", "show tool mode status", "tool first status"],
        Intent.TOOL_MODE_STATUS,
        0.95,
    ),
    (
        ["test left channel", "left channel test"],
        Intent.TEST_LEFT_CHANNEL,
        0.93,
    ),
    (
        ["test right channel", "right channel test"],
        Intent.TEST_RIGHT_CHANNEL,
        0.93,
    ),
    (
        ["test audio routing", "audio routing test"],
        Intent.TEST_AUDIO_ROUTING,
        0.93,
    ),
    (
        ["cycle audio output", "switch audio output", "next audio device"],
        Intent.CYCLE_AUDIO_OUTPUT,
        0.93,
    ),
    (
        [
            "show windows audio routing",
            "windows audio routing",
            "show playback routing",
        ],
        Intent.SHOW_WINDOWS_AUDIO_ROUTING,
        0.94,
    ),
    (
        [
            "cycle windows playback target",
            "cycle playback target",
            "next windows playback",
        ],
        Intent.CYCLE_WINDOWS_PLAYBACK_TARGET,
        0.94,
    ),
    (
        [
            "calibrate voice",
            "voice calibration",
            "calibrate speech",
        ],
        Intent.CALIBRATE_VOICE,
        0.94,
    ),
    (
        [
            "diagnose voice runtime",
            "voice runtime diagnostics",
            "diagnose audio runtime",
            "why can't i hear you",
            "why cant i hear you",
        ],
        Intent.DIAGNOSE_VOICE_RUNTIME,
        0.94,
    ),
    (
        [
            "reset jarvis runtime",
            "reset voice runtime",
            "reset overlay state",
            "stay open",
            "don't close",
            "dont close",
        ],
        Intent.RESET_JARVIS_RUNTIME,
        0.94,
    ),
    (
        [
            "show runtime status",
            "runtime status",
            "jarvis status",
            "מצב ריצה",
            "מצב ג'רוויס",
        ],
        Intent.SHOW_RUNTIME_STATUS,
        0.93,
    ),
    (
        ["show latency status", "latency status", "voice latency"],
        Intent.SHOW_LATENCY_STATUS,
        0.93,
    ),
    (
        [
            "show voice performance status",
            "voice performance status",
            "voice performance",
        ],
        Intent.SHOW_VOICE_PERFORMANCE_STATUS,
        0.93,
    ),
    # Phase 45 — read-only investigation engine
    (["phase 45 status", "phase45 status"], Intent.PHASE45_STATUS, 0.97),
    (["phase 46 status", "phase46 status"], Intent.PHASE46_STATUS, 0.97),
    (["inspect project"], Intent.INSPECT_PROJECT, 0.97),
    (
        ["inspect website project", "audit website project", "website project audit"],
        Intent.INSPECT_WEBSITE_PROJECT,
        0.97,
    ),
    (["summarize current project"], Intent.SUMMARIZE_CURRENT_PROJECT, 0.97),
    (["find failing tests"], Intent.FIND_FAILING_TESTS, 0.97),
    (["explain latest error"], Intent.EXPLAIN_LATEST_ERROR, 0.97),
    (
        ["investigate trading mismatch", "trading mismatch investigation"],
        Intent.INVESTIGATE_TRADING_MISMATCH,
        0.97,
    ),
    (
        ["compare live vs backtest", "compare backtest vs live"],
        Intent.COMPARE_LIVE_VS_BACKTEST,
        0.97,
    ),
    (["inspect latest live report"], Intent.INSPECT_LATEST_LIVE_REPORT, 0.97),
    (["inspect latest backtest report"], Intent.INSPECT_LATEST_BACKTEST_REPORT, 0.97),
    (["find recent code changes"], Intent.FIND_RECENT_CODE_CHANGES, 0.97),
    (["propose investigation plan"], Intent.PROPOSE_INVESTIGATION_PLAN, 0.97),
    (["run safe diagnostics"], Intent.RUN_SAFE_DIAGNOSTICS, 0.97),
    (["generate findings report"], Intent.GENERATE_FINDINGS_REPORT, 0.97),
    (["build investigation graph"], Intent.BUILD_INVESTIGATION_GRAPH, 0.97),
    (["show investigation graph"], Intent.SHOW_INVESTIGATION_GRAPH, 0.97),
    (["search investigation graph", "search graph"], Intent.SEARCH_INVESTIGATION_GRAPH, 0.94),
    (["trace algorithm behavior"], Intent.TRACE_ALGORITHM_BEHAVIOR, 0.97),
    (["diff live and backtest logic"], Intent.DIFF_LIVE_BACKTEST_LOGIC, 0.97),
    (["hunt algorithm bugs"], Intent.HUNT_ALGORITHM_BUGS, 0.97),
    (["propose algorithm patch"], Intent.PROPOSE_ALGORITHM_PATCH, 0.97),
    (["plan verification run"], Intent.PLAN_VERIFICATION_RUN, 0.97),
    (["replay symbol"], Intent.REPLAY_SYMBOL, 0.94),
    (["replay latest signal"], Intent.REPLAY_LATEST_SIGNAL, 0.97),
    (["replay live vs backtest"], Intent.REPLAY_LIVE_VS_BACKTEST, 0.94),
    (["verify top hypothesis"], Intent.VERIFY_TOP_HYPOTHESIS, 0.97),
    (["verify all hypotheses"], Intent.VERIFY_ALL_HYPOTHESES, 0.97),
    (["show replay timeline"], Intent.SHOW_REPLAY_TIMELINE, 0.97),
    (["show replay diff"], Intent.SHOW_REPLAY_DIFF, 0.94),
    (["build verification fixture"], Intent.BUILD_VERIFICATION_FIXTURE, 0.94),
    (["export replay snapshot"], Intent.EXPORT_REPLAY_SNAPSHOT, 0.94),
    (["trace signal lifecycle"], Intent.TRACE_SIGNAL_LIFECYCLE, 0.94),
    (["trace execution lifecycle"], Intent.TRACE_EXECUTION_LIFECYCLE, 0.94),
    (["show causality graph"], Intent.SHOW_CAUSALITY_GRAPH, 0.94),
    (["investigation confidence report"], Intent.INVESTIGATION_CONFIDENCE_REPORT, 0.97),
    (["simulate patch for top hypothesis"], Intent.SIMULATE_PATCH_TOP_HYPOTHESIS, 0.97),
    (["run patch simulation"], Intent.RUN_PATCH_SIMULATION, 0.97),
    (["compare replay before after"], Intent.COMPARE_REPLAY_BEFORE_AFTER, 0.97),
    (["estimate patch impact"], Intent.ESTIMATE_PATCH_IMPACT, 0.97),
    (["generate patch simulation report"], Intent.GENERATE_PATCH_SIMULATION_REPORT, 0.97),
    (["show patch simulation"], Intent.SHOW_PATCH_SIMULATION, 0.97),
    (["approve patch apply"], Intent.APPROVE_PATCH_APPLY, 0.97),
    (["reject patch apply"], Intent.REJECT_PATCH_APPLY, 0.97),
    (["run historical validation sweep"], Intent.RUN_HISTORICAL_VALIDATION_SWEEP, 0.97),
    (["show validation sweep"], Intent.SHOW_VALIDATION_SWEEP, 0.97),
    (["export validation sweep"], Intent.EXPORT_VALIDATION_SWEEP, 0.97),
    (["compare strategy metrics before after"], Intent.COMPARE_STRATEGY_METRICS_BEFORE_AFTER, 0.97),
    (["show worst divergence symbols"], Intent.SHOW_WORST_DIVERGENCE_SYMBOLS, 0.97),
    (["estimate production risk"], Intent.ESTIMATE_PRODUCTION_RISK, 0.97),
    (["recommend production action"], Intent.RECOMMEND_PRODUCTION_ACTION, 0.97),
    (["show investigation summary"], Intent.SHOW_INVESTIGATION_SUMMARY, 0.97),
    (["audit price integrity"], Intent.AUDIT_PRICE_INTEGRITY, 0.97),
    (["compare candle sources"], Intent.COMPARE_CANDLE_SOURCES, 0.97),
    (["trace price source"], Intent.TRACE_PRICE_SOURCE, 0.94),
    (["find close price mismatches"], Intent.FIND_CLOSE_PRICE_MISMATCHES, 0.97),
    (["inspect data cache drift"], Intent.INSPECT_DATA_CACHE_DRIFT, 0.97),
    (["check timestamp alignment"], Intent.CHECK_TIMESTAMP_ALIGNMENT, 0.97),
    (["check adjusted price usage"], Intent.CHECK_ADJUSTED_PRICE_USAGE, 0.97),
    (["check duplicate bars"], Intent.CHECK_DUPLICATE_BARS, 0.97),
    (["generate price integrity report"], Intent.GENERATE_PRICE_INTEGRITY_REPORT, 0.97),
    (["audit execution path"], Intent.AUDIT_EXECUTION_PATH, 0.97),
    (["explain zero execution attempts"], Intent.EXPLAIN_ZERO_EXECUTION_ATTEMPTS, 0.97),
    (["trace signal to order"], Intent.TRACE_SIGNAL_TO_ORDER, 0.94),
    (["show execution blockers"], Intent.SHOW_EXECUTION_BLOCKERS, 0.97),
    (["rank execution block reasons"], Intent.RANK_EXECUTION_BLOCK_REASONS, 0.97),
    (["inspect execution adapter"], Intent.INSPECT_EXECUTION_ADAPTER, 0.97),
    (["compare signal count to order attempts"], Intent.COMPARE_SIGNAL_COUNT_TO_ORDER_ATTEMPTS, 0.97),
    (["generate execution investigation report"], Intent.GENERATE_EXECUTION_INVESTIGATION_REPORT, 0.97),
    (["trace signal to execution"], Intent.TRACE_SIGNAL_TO_EXECUTION, 0.94),
    (["trace blocked signal"], Intent.TRACE_BLOCKED_SIGNAL, 0.94),
    (["explain top execution blocker"], Intent.EXPLAIN_TOP_EXECUTION_BLOCKER, 0.97),
    (["reconstruct execution flow"], Intent.RECONSTRUCT_EXECUTION_FLOW, 0.97),
    (["show signal lifecycle timeline"], Intent.SHOW_SIGNAL_LIFECYCLE_TIMELINE, 0.97),
    (["rank dead signal causes"], Intent.RANK_DEAD_SIGNAL_CAUSES, 0.97),
    (["simulate unblock scenario"], Intent.SIMULATE_UNBLOCK_SCENARIO, 0.94),
    (["propose execution fix"], Intent.PROPOSE_EXECUTION_FIX, 0.97),
    (["generate execution flow report"], Intent.GENERATE_EXECUTION_FLOW_REPORT, 0.97),
    (["simulate execution cleanup patch"], Intent.SIMULATE_EXECUTION_CLEANUP_PATCH, 0.97),
    (["compare risk before after cleanup"], Intent.COMPARE_RISK_BEFORE_AFTER_CLEANUP, 0.97),
    (["show stale open positions"], Intent.SHOW_STALE_OPEN_POSITIONS, 0.97),
    (["propose execution cleanup patch"], Intent.PROPOSE_EXECUTION_CLEANUP_PATCH, 0.97),
    (["generate execution cleanup report"], Intent.GENERATE_EXECUTION_CLEANUP_REPORT, 0.97),
    (["show approved patch"], Intent.SHOW_APPROVED_PATCH, 0.97),
    (["validate patch safety", "validate patch safe"], Intent.VALIDATE_PATCH_SAFETY, 0.97),
    (["apply approved patch"], Intent.APPLY_APPROVED_PATCH, 0.97),
    (["apply approved patch confirm"], Intent.APPLY_APPROVED_PATCH, 0.97),
    (["rollback last patch"], Intent.ROLLBACK_LAST_PATCH, 0.97),
    (["rollback last patch confirm"], Intent.ROLLBACK_LAST_PATCH, 0.97),
    (["show patch history"], Intent.SHOW_PATCH_HISTORY, 0.97),
    (["validate applied patch"], Intent.VALIDATE_APPLIED_PATCH, 0.97),
    (["replay after patch", "replay validation", "replay patch validation"], Intent.REPLAY_AFTER_PATCH, 0.97),
    (["compare pre post patch", "compare pre and post patch"], Intent.COMPARE_PRE_POST_PATCH, 0.97),
    (["run patch workflow"], Intent.RUN_PATCH_WORKFLOW, 0.97),
    (["run patch workflow confirm"], Intent.RUN_PATCH_WORKFLOW, 0.97),
    (["show patch workflow status", "patch workflow status"], Intent.SHOW_PATCH_WORKFLOW_STATUS, 0.97),
    (["show runtime health", "runtime health"], Intent.SHOW_RUNTIME_HEALTH, 0.97),
    (["show healing actions", "healing actions"], Intent.SHOW_HEALING_ACTIONS, 0.97),
    (["show stuck workers", "stuck workers"], Intent.SHOW_STUCK_WORKERS, 0.97),
    (["recover overlay", "recover overlay confirm"], Intent.RECOVER_OVERLAY, 0.97),
    (["recover voice system", "recover voice system confirm"], Intent.RECOVER_VOICE_SYSTEM, 0.97),
    (["restart dashboard", "restart dashboard confirm"], Intent.RESTART_DASHBOARD, 0.97),
    (["restart wake listener", "restart wake listener confirm"], Intent.RESTART_WAKE_LISTENER, 0.97),
    (["restart operator console", "restart operator console confirm"], Intent.RESTART_OPERATOR_CONSOLE, 0.97),
    (["clear stale locks", "clear stale locks confirm"], Intent.CLEAR_STALE_LOCKS, 0.97),
    (["validate runtime integrity"], Intent.VALIDATE_RUNTIME_INTEGRITY, 0.97),
    (["phase 49 status"], Intent.PHASE49_STATUS, 0.97),
    (["what am i looking at"], Intent.WHAT_AM_I_LOOKING_AT, 0.97),
    (["summarize my screen", "summarize current screen"], Intent.SUMMARIZE_CURRENT_SCREEN, 0.97),
    (["summarize trading health"], Intent.SUMMARIZE_TRADING_HEALTH, 0.97),
    (["explain why no trades today"], Intent.EXPLAIN_WHY_NO_TRADES_TODAY, 0.97),
    (["compare today vs yesterday"], Intent.COMPARE_TODAY_VS_YESTERDAY, 0.97),
    (["show top operational blockers"], Intent.SHOW_TOP_OPERATIONAL_BLOCKERS, 0.97),
    (["show current execution risk"], Intent.SHOW_CURRENT_EXECUTION_RISK, 0.97),
    (["summarize live engine status"], Intent.SUMMARIZE_LIVE_ENGINE_STATUS, 0.97),
    (["resume last task"], Intent.RESUME_LAST_TASK, 0.97),
    (["what was i doing"], Intent.RESUME_LAST_TASK, 0.96),
    (["show recent investigations"], Intent.SHOW_RECENT_INVESTIGATIONS, 0.97),
    (["continue investigation", "continue previous investigation"], Intent.CONTINUE_INVESTIGATION, 0.97),
    (["open last report", "open latest report"], Intent.OPEN_LAST_REPORT, 0.97),
    (["search reports"], Intent.SEARCH_REPORTS, 0.94),
    (["show current state"], Intent.SHOW_CURRENT_STATE, 0.97),
    (["show active systems"], Intent.SHOW_ACTIVE_SYSTEMS, 0.97),
    (["show runtime summary"], Intent.SHOW_RUNTIME_SUMMARY, 0.97),
    (["show operational suggestions"], Intent.SHOW_OPERATIONAL_SUGGESTIONS, 0.97),
    (["phase 50 status"], Intent.PHASE50_STATUS, 0.97),
    # Trading / operating layer (Phases 22–23) — before generic start_task (substring overlap)
    (
        ["review trading algorithm", "deep review trading"],
        Intent.REVIEW_TRADING_ALGORITHM,
        0.94,
    ),
    (
        ["compare backtest to paper", "backtest vs paper"],
        Intent.COMPARE_BACKTEST_TO_PAPER,
        0.94,
    ),
    (
        ["find live backtest mismatch", "live backtest mismatch"],
        Intent.FIND_LIVE_BACKTEST_MISMATCH,
        0.93,
    ),
    (
        ["generate backtest paper report", "backtest paper report"],
        Intent.GENERATE_BACKTEST_PAPER_REPORT,
        0.91,
    ),
    # Supervised task agent (Phase 19)
    (
        [
            "review my trading algorithm",
            "compare backtest to paper trading",
            "investigate why dashboard is down",
            "build a report about recent trading failures",
            "start supervised task",
            "start task",
        ],
        Intent.START_TASK,
        0.92,
    ),
    (["show task plan", "task plan"], Intent.SHOW_TASK_PLAN, 0.93),
    (
        ["approve task plan", "approve the task plan", "approve task"],
        Intent.APPROVE_TASK_PLAN,
        0.93,
    ),
    (["run task step", "run next task step", "execute task step"], Intent.RUN_TASK_STEP, 0.93),
    (["stop task", "cancel task", "abort task"], Intent.STOP_TASK, 0.93),
    (["show task status", "task status"], Intent.SHOW_TASK_STATUS, 0.93),
    (["show task report", "task report"], Intent.SHOW_TASK_REPORT, 0.93),
    (["show task findings", "task findings"], Intent.SHOW_TASK_FINDINGS, 0.93),
    (["propose task patch", "propose patch"], Intent.PROPOSE_TASK_PATCH, 0.92),
    (["show task patch"], Intent.SHOW_TASK_PATCH, 0.93),
    (["propose task patch"], Intent.PROPOSE_TASK_PATCH, 0.93),
    (["approve task patch"], Intent.APPROVE_TASK_PATCH, 0.93),
    (["reject task patch"], Intent.REJECT_TASK_PATCH, 0.93),
    (["apply task patch"], Intent.APPLY_TASK_PATCH, 0.93),
    (["rollback task patch"], Intent.ROLLBACK_TASK_PATCH, 0.93),
    (["show last diff", "last diff"], Intent.SHOW_LAST_DIFF, 0.92),
    (["plan experiments", "experiment grid"], Intent.PLAN_EXPERIMENTS, 0.9),
    (["queue task"], Intent.QUEUE_TASK, 0.9),
    (["show task queue", "task queue"], Intent.SHOW_TASK_QUEUE, 0.92),
    (["pause task queue"], Intent.PAUSE_TASK_QUEUE, 0.92),
    (["resume task queue"], Intent.RESUME_TASK_QUEUE, 0.92),
    (
        ["start trading workspace", "trading workspace"],
        Intent.START_TRADING_WORKSPACE,
        0.95,
    ),
    (["start study workspace", "study workspace"], Intent.START_STUDY_WORKSPACE, 0.95),
    (["start dev workspace", "dev workspace"], Intent.START_DEV_WORKSPACE, 0.95),
    (["suggest ui click"], Intent.SUGGEST_UI_CLICK, 0.88),
    (["confirm ui click"], Intent.CONFIRM_UI_CLICK, 0.9),
    (["browser dom read", "read dashboard dom"], Intent.BROWSER_DOM_READ, 0.88),
    (["build presentation about"], Intent.BUILD_PRESENTATION, 0.85),
    (["create report about"], Intent.CREATE_REPORT_DOCUMENT, 0.85),
    (["show startup health", "startup health"], Intent.SHOW_STARTUP_HEALTH, 0.9),
    (["show settings status", "settings status"], Intent.SHOW_SETTINGS_STATUS, 0.9),
    (
        [
            "show jarvis status",
            "jarvis status",
            "jarvis status center",
            "how are you running",
            "how are you doing",
            "what's your status",
            "whats your status",
            "what is your status",
            "are you online",
            "system status jarvis",
        ],
        Intent.SHOW_JARVIS_STATUS,
        0.94,
    ),
    (
        [
            "show diagnostics",
            "show me diagnostics",
            "run diagnostics",
            "system diagnostics",
        ],
        Intent.RUN_DIAGNOSTICS,
        0.93,
    ),
    (
        [
            "describe screen",
            "what's on my screen",
            "whats on my screen",
            "analyze my screen",
            "screen analysis",
        ],
        Intent.DESCRIBE_SCREEN,
        0.93,
    ),
    (
        ["show command audit", "command audit", "show audit trail"],
        Intent.SHOW_COMMAND_AUDIT,
        0.94,
    ),
    (["show overlay"], Intent.SHOW_OVERLAY, 0.94),
    (["hide overlay"], Intent.HIDE_OVERLAY, 0.94),
    (["toggle quiet mode", "quiet mode"], Intent.TOGGLE_QUIET_MODE, 0.93),
    (["show approvals", "approval inbox", "list approvals"], Intent.SHOW_APPROVALS, 0.94),
    (
        ["approve pending action"],
        Intent.APPROVE_PENDING_ACTION,
        0.94,
    ),
    (
        ["reject pending action"],
        Intent.REJECT_PENDING_ACTION,
        0.94,
    ),
    (["clear approvals", "clear approval inbox"], Intent.CLEAR_APPROVALS, 0.93),
    # System
    (
        ["מה מצב המחשב", "system status", "cpu ram"],
        Intent.SHOW_SYSTEM_STATUS,
        0.90,
    ),
    (["שימוש בדיסק", "disk usage", "show disk usage"], Intent.SHOW_DISK_USAGE, 0.88),
    (
        ["מצב רשת", "network status", "show network status"],
        Intent.SHOW_NETWORK_STATUS,
        0.88,
    ),
    (["shutdown jarvis", "exit jarvis", "סגור את ג'רוויס"], Intent.SHUTDOWN_JARVIS, 0.95),
]

_KEYWORD_RULES: list[tuple[list[str], Intent, float]] = [
    (["קרסור", "cursor"], Intent.OPEN_CURSOR, 0.75),
    (["כרום", "chrome"], Intent.OPEN_CHROME, 0.75),
    (["טרמינל", "terminal"], Intent.OPEN_TERMINAL, 0.76),
    (["דאשבורד", "dashboard"], Intent.OPEN_TRADING_DASHBOARD, 0.72),
    (["בריאות דאשבורד", "dashboard health", "חי"], Intent.SHOW_DASHBOARD_HEALTH, 0.78),
    (["יומי", "daily loop"], Intent.RUN_LIVE_DAILY_LOOP, 0.72),
    (["שבועי", "weekly loop"], Intent.RUN_LIVE_WEEKLY_LOOP, 0.70),
    (["פוזיצ", "positions"], Intent.SHOW_OPEN_POSITIONS, 0.72),
    (["שגיאות", "errors", "error"], Intent.SHOW_LAST_ERRORS, 0.74),
    (["דחיות", "rejection"], Intent.SHOW_REJECTION_REASONS, 0.72),
    (["חסומים", "blocked trade"], Intent.SHOW_BLOCKED_TRADES, 0.72),
    (["סכם", "summarize"], Intent.SUMMARIZE_LATEST_LOG, 0.70),
    (["חפש בלוג", "search log"], Intent.SEARCH_TRADING_LOGS, 0.72),
    (["חפש קובץ", "fib_quality"], Intent.SEARCH_PROJECT_FILE_BY_NAME, 0.75),
    (["חפש בקוד", "max_positions"], Intent.SEARCH_CODE_TEXT, 0.74),
    (["פונקציה", "function"], Intent.FIND_FUNCTION, 0.72),
    (["מחלקה", "class"], Intent.FIND_CLASS, 0.70),
    (["risk_per_trade", "exposure_limit"], Intent.FIND_RISK_USAGE, 0.85),
    (["delayed_entry"], Intent.FIND_DELAYED_ENTRY_LOGIC, 0.85),
    (["execution_event", "place_order"], Intent.FIND_EXECUTION_EVENTS_LOGIC, 0.82),
    (["דוח", "report"], Intent.SHOW_LATEST_LIVE_REPORT, 0.68),
    (["מחשב", "cpu", "ram"], Intent.SHOW_SYSTEM_STATUS, 0.72),
    (["דיסק", "disk"], Intent.SHOW_DISK_USAGE, 0.72),
    (["רשת", "network"], Intent.SHOW_NETWORK_STATUS, 0.72),
    (["shutdown", "exit jarvis"], Intent.SHUTDOWN_JARVIS, 0.80),
]


# ---------------------------------------------------------------------------
# Phase 72 — bounded read-only tool-use commands (highest priority, anchored).
# Only three commands are exposed; each is matched explicitly so it cannot be
# hijacked by, or hijack, other intents.
# ---------------------------------------------------------------------------
_TOOL_SHOW_LAST_RE = re.compile(r"^\s*show\s+last\s+(?:tool\s+run|web\s+task)\s*$", re.I)
_TOOL_PLAN_RE = re.compile(r"^\s*(?:plan\s+tool\s+task|preview\s+web\s+task)\s+(.+?)\s*$", re.I)
_TOOL_RUN_RE = re.compile(
    r"^\s*(?:run\s+tool\s+task|research|look\s+up)\s+(.+?)(?:\s+and\s+summari[sz]e)?\s*$",
    re.I,
)


def match_tool_use_command(text: str):
    """Match the 3 Phase 72 tool-use commands. Returns CommandRequest or None."""
    t = (text or "").strip()
    if not t:
        return None
    if _TOOL_SHOW_LAST_RE.match(t):
        return CommandRequest(
            raw_text=text, intent=Intent.SHOW_LAST_TOOL_RUN,
            confidence=0.97, classifier_source="tool_use",
        )
    m = _TOOL_PLAN_RE.match(t)
    if m:
        return CommandRequest(
            raw_text=text, intent=Intent.PLAN_TOOL_TASK,
            confidence=0.96, params={"goal": m.group(1).strip()},
            classifier_source="tool_use",
        )
    m = _TOOL_RUN_RE.match(t)
    if m:
        return CommandRequest(
            raw_text=text, intent=Intent.RUN_TOOL_TASK,
            confidence=0.96, params={"goal": m.group(1).strip()},
            classifier_source="tool_use",
        )
    return None


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).strip().lower()
    return re.sub(r"\s+", " ", text)


def _phrase_matches(normalized: str, phrase: str) -> bool:
    if phrase == normalized:
        return True
    if phrase in normalized:
        return True
    if normalized in phrase:
        # Avoid false positives like "oh" matching inside "yohananof".
        if len(normalized) < 4:
            return False
        return True
    return False


def _match_special(text: str, normalized: str) -> CommandRequest | None:
    """High-specificity patterns with captured params."""
    from brain.patch_command_phrases import is_patch_workflow_phrase, match_patch_workflow_commands

    patch_match = match_patch_workflow_commands(text)
    if patch_match is not None:
        return patch_match

    try:
        from voice.stt_stack.voice_fingerprint import grammar_min_score_for_user

        min_score = grammar_min_score_for_user()
    except Exception:
        from config import VOICE_GRAMMAR_MIN_SCORE

        min_score = VOICE_GRAMMAR_MIN_SCORE
    from brain.command_grammar import match_command_grammar_as_request

    grammar = match_command_grammar_as_request(text, min_score=min_score)
    if grammar is not None:
        return grammar

    from brain.english_voice_phrases import match_english_voice_phrase

    english = match_english_voice_phrase(text)
    if english is not None:
        return english

    if normalized in ("show memory graph", "memory graph", "show knowledge graph"):
        return CommandRequest(
            raw_text=text,
            intent=Intent.SHOW_MEMORY_GRAPH,
            confidence=0.94,
            classifier_source="rules",
        )

    from browser.url_parser import extract_first_url, is_probable_url

    raw_url = extract_first_url(text)
    if raw_url and any(token in normalized for token in ("open website", "go to", "navigate to", "browse to", "open ", "launch ", "start ")):
        return CommandRequest(
            raw_text=text,
            intent=Intent.OPEN_WEBSITE,
            confidence=0.96,
            params={"url": raw_url},
            classifier_source="rules",
        )
    if is_probable_url(normalized) and any(token in normalized for token in ("go to", "navigate to", "browse to")):
        return CommandRequest(
            raw_text=text,
            intent=Intent.OPEN_WEBSITE,
            confidence=0.95,
            params={"url": normalized.split(maxsplit=2)[-1]},
            classifier_source="rules",
        )

    m = re.search(
        r"search\s+(?:memory|knowledge)\s+graph(?:\s+(.+))?$|find\s+memory\s+link(?:\s+(.+))?$|graph\s+search(?:\s+(.+))?$",
        text,
        re.I,
    )
    if m:
        query = (m.group(1) or m.group(2) or m.group(3) or "").strip()
        return CommandRequest(
            raw_text=text,
            intent=Intent.SEARCH_MEMORY_GRAPH,
            confidence=0.94,
            params={"query": query},
            classifier_source="rules",
        )

    if normalized == "show dashboard":
        return CommandRequest(
            raw_text=text,
            intent=Intent.OPEN_TRADING_DASHBOARD,
            confidence=0.95,
            classifier_source="rules",
        )

    workspace_map = {
        "start trading workspace": Intent.START_TRADING_WORKSPACE,
        "trading workspace": Intent.START_TRADING_WORKSPACE,
        "start study workspace": Intent.START_STUDY_WORKSPACE,
        "study workspace": Intent.START_STUDY_WORKSPACE,
        "start dev workspace": Intent.START_DEV_WORKSPACE,
        "dev workspace": Intent.START_DEV_WORKSPACE,
    }
    if normalized in workspace_map:
        return CommandRequest(
            raw_text=text,
            intent=workspace_map[normalized],
            confidence=0.96,
            classifier_source="rules",
        )

    m = re.search(
        r"^(?:open|launch|start|go to|navigate to|browse to)\s+(.+)$|^(?:פתח)\s+(.+)$",
        normalized,
        re.I,
    )
    if m:
        app_name = (m.group(1) or m.group(2) or "").strip()
        from browser.url_parser import is_probable_url

        if is_probable_url(app_name):
            return CommandRequest(
                raw_text=text,
                intent=Intent.OPEN_WEBSITE,
                confidence=0.95,
                params={"url": app_name},
                classifier_source="rules",
            )
        from apps.discovery import normalize_app_query

        from websites.registry import find_website_match, get_builtin, normalize_website_query

        site_key = normalize_website_query(app_name)
        site_builtin = get_builtin(site_key)
        if site_builtin is not None:
            return CommandRequest(
                raw_text=text,
                intent=Intent.OPEN_WEBSITE,
                confidence=0.92,
                params={"website": site_builtin.site_id},
                classifier_source="rules",
            )
        web_matches, _ = find_website_match(app_name)
        if len(web_matches) == 1 and web_matches[0].builtin:
            return CommandRequest(
                raw_text=text,
                intent=Intent.OPEN_WEBSITE,
                confidence=0.92,
                params={"website": web_matches[0].site_id},
                classifier_source="rules",
            )

        from apps.discovery import normalize_app_query

        app_key = normalize_app_query(app_name)
        reserved = {
            "dashboard",
            "trading_dashboard",
            "cursor",
            "chrome",
            "terminal",
            "task_manager",
            "file_explorer",
            "project_folder",
            "latest_log",
            "chatgpt",
            "tradingview",
            "youtube",
            "gmail",
            "google",
            "github",
            "yohananof",
            "openai",
        }
        if "דאשבורד" in app_name or "dashboard" in app_name:
            app_key = "dashboard"
        if app_key and app_key not in reserved:
            return CommandRequest(
                raw_text=text,
                intent=Intent.OPEN_APP,
                confidence=0.92,
                params={"app": app_key},
                classifier_source="rules",
            )

    m = re.search(
        r"search apps?\s+(.+)|חפש אפליקציות\s+(.+)",
        text,
        re.I,
    )
    if m:
        query = (m.group(1) or m.group(2) or "").strip()
        return CommandRequest(
            raw_text=text,
            intent=Intent.SEARCH_APPS,
            confidence=0.92,
            params={"query": query},
            classifier_source="rules",
        )

    if "פקודות מסחר" in normalized or "trading commands" in normalized:
        return CommandRequest(
            raw_text=text,
            intent=Intent.EXPLAIN_SKILL,
            confidence=0.92,
            params={"skill": "trading"},
        )
    if "תסביר" in normalized and ("לוג" in normalized or "log" in normalized):
        return CommandRequest(
            raw_text=text,
            intent=Intent.EXPLAIN_SKILL,
            confidence=0.9,
            params={"skill": "logs"},
        )
    m = re.search(
        r"help\s+(?:for\s+)?(.+)|תן עזרה על\s+(.+)|איך אני מריץ\s+(.+)",
        text,
        re.I,
    )
    if m:
        query = (m.group(1) or m.group(2) or m.group(3) or "").strip()
        return CommandRequest(
            raw_text=text,
            intent=Intent.HELP_FOR_COMMAND,
            confidence=0.9,
            params={"query": query},
        )
    m = re.search(
        r"חפש בלוגים\s+(.+)|search(?:\s+trading)?\s+logs\s+(.+)",
        text,
        re.I,
    )
    if m:
        query = (m.group(1) or m.group(2) or "").strip()
        return CommandRequest(
            raw_text=text,
            intent=Intent.SEARCH_TRADING_LOGS,
            confidence=0.9,
            params={"query": query},
        )

    m = re.search(
        r"חפש קובץ\s+(.+)|search\s+file\s+(.+)|fib_quality",
        text,
        re.I,
    )
    if m:
        query = (m.group(1) or m.group(2) or "fib_quality").strip()
        return CommandRequest(
            raw_text=text,
            intent=Intent.SEARCH_PROJECT_FILE_BY_NAME,
            confidence=0.9,
            params={"query": query},
        )

    m = re.search(
        r"חפש בקוד\s+(.+)|search\s+code\s+(.+)|max_positions_reached",
        text,
        re.I,
    )
    if m:
        query = (m.group(1) or m.group(2) or "max_positions_reached").strip()
        return CommandRequest(
            raw_text=text,
            intent=Intent.SEARCH_CODE_TEXT,
            confidence=0.9,
            params={"query": query},
        )

    m = re.search(
        r"חפש פונקציה\s+(\w+)|find function\s+(\w+)|generate_trades",
        text,
        re.I,
    )
    if m:
        name = (m.group(1) or m.group(2) or "generate_trades").strip()
        return CommandRequest(
            raw_text=text,
            intent=Intent.FIND_FUNCTION,
            confidence=0.9,
            params={"name": name},
        )

    m = re.search(
        r"חפש מחלקה\s+(\w+)|find class\s+(\w+)|PortfolioManager",
        text,
        re.I,
    )
    if m:
        name = (m.group(1) or m.group(2) or "PortfolioManager").strip()
        return CommandRequest(
            raw_text=text,
            intent=Intent.FIND_CLASS,
            confidence=0.9,
            params={"name": name},
        )

    if normalized in (
        "read what is on screen",
        "read what is on the screen",
    ):
        return CommandRequest(
            raw_text=text,
            intent=Intent.READ_SCREEN_TEXT,
            confidence=0.95,
            classifier_source="rules",
        )

    m = re.search(
        r"find\s+on\s+screen\s+(.+)$|find\s+this\s+on\s+screen\s+(.+)$",
        normalized,
        re.I,
    )
    if m:
        query = (m.group(1) or m.group(2) or "").strip()
        return CommandRequest(
            raw_text=text,
            intent=Intent.FIND_ON_SCREEN,
            confidence=0.94,
            params={"query": query},
            classifier_source="rules",
        )

    m = re.search(r"where\s+is\s+(.+?)\s+on\s+(?:the\s+)?screen\s*$", normalized, re.I)
    if m:
        query = m.group(1).strip()
        return CommandRequest(
            raw_text=text,
            intent=Intent.FIND_ON_SCREEN,
            confidence=0.93,
            params={"query": query},
            classifier_source="rules",
        )

    if "איפה מוגדר" in normalized or (
        "where is" in normalized and "on screen" not in normalized
    ):
        key_match = re.search(
            r"(risk_per_trade|max_positions|exposure_limit|[\w.]+)\s*$",
            normalized,
        )
        key = key_match.group(1) if key_match else ""
        if "risk" in normalized:
            return CommandRequest(
                raw_text=text,
                intent=Intent.FIND_RISK_USAGE,
                confidence=0.88,
            )
        if key:
            return CommandRequest(
                raw_text=text,
                intent=Intent.FIND_CONFIG_KEY,
                confidence=0.85,
                params={"key": key},
            )

    if "delayed_entry_failed" in normalized:
        return CommandRequest(
            raw_text=text,
            intent=Intent.SEARCH_TRADING_LOGS,
            confidence=0.9,
            params={"query": "delayed_entry_failed"},
        )

    m = re.search(
        r"alias[:\s]+(.+?)\s*=\s*([\w_]+)|פתח\s+מסחר\s*=\s*(\w+)",
        text,
        re.I,
    )
    if m:
        alias = (m.group(1) or "פתח מסחר").strip()
        intent_name = (m.group(2) or m.group(3) or "").strip()
        return CommandRequest(
            raw_text=text,
            intent=Intent.SET_ALIAS,
            confidence=0.92,
            params={"alias": alias, "intent": intent_name},
        )

    if "זכור שכאשר" in normalized and "אומר" in normalized:
        return CommandRequest(
            raw_text=text,
            intent=Intent.SET_ALIAS,
            confidence=0.9,
        )

    m = re.search(
        r"run workflow\s+([\w_]+)|תריץ workflow\s+([\w_]+)|(?<!patch\s)workflow\s+([\w_]+)",
        text,
        re.I,
    )
    if m and not is_patch_workflow_phrase(text):
        wf_name = (m.group(1) or m.group(2) or m.group(3) or "").strip().lower()
        if wf_name in ("list", "explain"):
            return None
        return CommandRequest(
            raw_text=text,
            intent=Intent.RUN_WORKFLOW,
            confidence=0.92,
            params={"workflow": wf_name},
        )

    m = re.search(
        r"explain workflow\s+([\w_]+)|תסביר workflow\s+([\w_]+)",
        text,
        re.I,
    )
    if m:
        wf_name = (m.group(1) or m.group(2) or "").strip().lower()
        return CommandRequest(
            raw_text=text,
            intent=Intent.EXPLAIN_WORKFLOW,
            confidence=0.92,
            params={"workflow": wf_name},
        )

    if "תריץ בדיקת מערכת מסחר" in normalized:
        return CommandRequest(
            raw_text=text,
            intent=Intent.RUN_WORKFLOW,
            confidence=0.95,
            params={"workflow": "trading_health_check"},
        )
    if "בדוק שגיאות במסך" in normalized:
        return CommandRequest(
            raw_text=text,
            intent=Intent.RUN_WORKFLOW,
            confidence=0.94,
            params={"workflow": "screen_error_check"},
        )

    m = re.search(
        r"focus window\s+(.+)|תעביר פוקוס ל(.+)|focus\s+(.+)",
        text,
        re.I,
    )
    if m:
        title = (m.group(1) or m.group(2) or m.group(3) or "").strip()
        return CommandRequest(
            raw_text=text,
            intent=Intent.FOCUS_WINDOW,
            confidence=0.92,
            params={"title": title},
        )

    m = re.search(
        r"minimize window\s+(.+)|מזער חלון\s+(.+)|מזער את\s+(.+)",
        text,
        re.I,
    )
    if m:
        title = (m.group(1) or m.group(2) or m.group(3) or "").strip()
        return CommandRequest(
            raw_text=text,
            intent=Intent.MINIMIZE_WINDOW,
            confidence=0.9,
            params={"title": title},
        )

    m = re.search(
        r"maximize window\s+(.+)|הגדל חלון\s+(.+)|הגדל את\s+(.+)",
        text,
        re.I,
    )
    if m:
        title = (m.group(1) or m.group(2) or m.group(3) or "").strip()
        return CommandRequest(
            raw_text=text,
            intent=Intent.MAXIMIZE_WINDOW,
            confidence=0.9,
            params={"title": title},
        )

    m = re.search(
        r"copy\s+(.+?)\s+to clipboard|העתק\s+(.+?)\s+לקליפבורד|העתק את הטקסט\s+(.+?)\s+לקליפבורד",
        text,
        re.I,
    )
    if m:
        content = (m.group(1) or m.group(2) or m.group(3) or "").strip()
        return CommandRequest(
            raw_text=text,
            intent=Intent.COPY_TEXT_TO_CLIPBOARD,
            confidence=0.9,
            params={"text": content},
        )

    return None


def _session_to_context(session: object | None) -> dict | None:
    if session is None:
        return None
    ctx = {
        "last_intent": getattr(session, "last_intent", "") or "",
        "last_opened_log": getattr(session, "last_opened_log", "") or "",
        "last_report_path": getattr(session, "last_report_path", "") or "",
        "last_command_text": getattr(session, "last_command_text", "") or "",
    }
    try:
        from brain.memory import safe_memory_summary
        from brain.aliases import get_aliases

        ctx["memory"] = safe_memory_summary()
        ctx["aliases"] = [a["alias"] for a in get_aliases().list_aliases()[:10]]
    except Exception:
        pass
    try:
        from conversation.context_store import get_classify_context

        conv = get_classify_context()
        if conv:
            ctx["conversation"] = conv
            if conv.get("last_intent") and not ctx.get("last_intent"):
                ctx["last_intent"] = conv["last_intent"]
    except Exception:
        pass
    return ctx


def classify_rules(text: str) -> CommandRequest:
    """Rule-based classifier only."""
    from brain.operational_command_phrases import match_operational_priority_commands
    from brain.patch_command_phrases import match_patch_workflow_commands

    tool_req = match_tool_use_command(text)
    if tool_req is not None:
        return tool_req

    operational = match_operational_priority_commands(text)
    if operational is not None:
        operational.classifier_source = "operational_phrases"
        return operational

    patch_req = match_patch_workflow_commands(text)
    if patch_req is not None:
        patch_req.classifier_source = "patch_workflow"
        return patch_req

    try:
        from voice.command_input import prepare_command_text

        text = prepare_command_text(text)
    except Exception:
        pass
    normalized = _normalize(text)
    if not normalized:
        return CommandRequest(
            raw_text=text,
            intent=Intent.UNKNOWN,
            confidence=0.0,
            classifier_source="rules",
        )

    special = _match_special(text, normalized)
    if special is not None:
        special.language = "he" if re.search(r"[\u0590-\u05FF]", text) else "en"
        special.classifier_source = "rules"
        return special

    best_intent = Intent.UNKNOWN
    best_confidence = 0.0

    for phrases, intent, confidence in _PHRASE_RULES:
        for phrase in phrases:
            p = _normalize(phrase)
            if _phrase_matches(normalized, p):
                if confidence > best_confidence:
                    best_intent = intent
                    best_confidence = confidence

    if best_confidence < CONFIDENCE_THRESHOLD:
        for keys, intent, conf in _KEYWORD_RULES:
            if any(k in normalized for k in keys):
                if conf > best_confidence:
                    best_intent = intent
                    best_confidence = conf

    if best_confidence < CONFIDENCE_THRESHOLD:
        if best_confidence > 0.4:
            return CommandRequest(
                raw_text=text,
                intent=Intent.CLARIFY,
                confidence=best_confidence,
                classifier_source="rules",
            )
        return CommandRequest(
            raw_text=text,
            intent=Intent.UNKNOWN,
            confidence=best_confidence,
            classifier_source="rules",
        )

    return CommandRequest(
        raw_text=text,
        intent=best_intent,
        confidence=best_confidence,
        language="he" if re.search(r"[\u0590-\u05FF]", text) else "en",
        classifier_source="rules",
    )


def classify(
    text: str,
    session_context: object | None = None,
) -> CommandRequest:
    """
    Hybrid understanding: rules/grammar → semantic → optional semantic LLM → legacy LLM.
    Router/security/registry remain authoritative after classification.
    """
    from brain.operational_command_phrases import match_operational_priority_commands
    from brain.patch_command_phrases import match_patch_workflow_commands

    # Phase 72 — tool-use commands are matched first, deterministically,
    # ahead of semantic/LLM layers so they cannot be misrouted.
    tool_req = match_tool_use_command(text)
    if tool_req is not None:
        return tool_req

    operational = match_operational_priority_commands(text)
    if operational is not None:
        return operational

    patch_req = match_patch_workflow_commands(text)
    if patch_req is not None:
        return patch_req

    try:
        from brain.instant_fast_lane import match_instant_fast_lane

        fast_req = match_instant_fast_lane(text)
        if (
            fast_req is not None
            and fast_req.confidence >= 0.85
            and fast_req.intent not in (Intent.UNKNOWN, Intent.CLARIFY)
        ):
            return fast_req
    except Exception:
        pass

    semantic_req: CommandRequest | None = None
    try:
        from config import SEMANTIC_UNDERSTANDING_ENABLED

        if SEMANTIC_UNDERSTANDING_ENABLED:
            from language.hybrid_understanding import classify_hybrid

            semantic_req, _sem = classify_hybrid(text, session_context)
            if not LLM_CLASSIFIER_ENABLED:
                return semantic_req
            if (
                semantic_req.confidence >= CONFIDENCE_THRESHOLD
                and semantic_req.intent not in (Intent.UNKNOWN, Intent.CLARIFY)
            ):
                return semantic_req
    except Exception:
        pass

    rule_req = classify_rules(text)

    if not LLM_CLASSIFIER_ENABLED:
        return rule_req

    if (
        rule_req.confidence >= CONFIDENCE_THRESHOLD
        and rule_req.intent not in (Intent.UNKNOWN, Intent.CLARIFY)
    ):
        return rule_req

    from brain.llm_intent_classifier import (
        LLMIntentClassifier,
        classification_to_request,
    )

    llm = LLMIntentClassifier()
    ctx = _session_to_context(session_context)
    ic = llm.classify(text, session_context=ctx)

    if ic.valid:
        return classification_to_request(text, ic)

    if LLM_FALLBACK_TO_RULES:
        if rule_req.intent not in (Intent.UNKNOWN,) or rule_req.confidence > 0:
            return rule_req.model_copy(update={"classifier_source": "fallback"})
        if semantic_req is not None:
            return semantic_req.model_copy(update={"classifier_source": "fallback"})
        return rule_req

    return CommandRequest(
        raw_text=text,
        intent=Intent.CLARIFY,
        confidence=ic.confidence,
        classifier_source="clarification",
    )


from core.intent_validation import assert_phrase_table_valid

assert_phrase_table_valid(_PHRASE_RULES, source="intent_classifier", expected_row_len=3)
