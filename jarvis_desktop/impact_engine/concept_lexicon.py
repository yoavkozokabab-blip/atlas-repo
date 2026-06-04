"""Phase 137 — framework-agnostic concept lexicon + generic concept resolver.

Phase 136 proved Syron's impact concept resolution was Home-Assistant-biased: a
hand-curated ``CONCEPT_TARGET_MAP`` only knew HA's subsystems, so cross-cutting
concepts (logging, events, background jobs, scheduling, state management,
plugins, api layer, …) resolved at 0% on every non-HA repo.

This module generalizes resolution by deriving targets from the repository's OWN
structure — filenames, directory names and mined symbols — rather than a fixed
catalogue. It is used as a FALLBACK when the curated map misses, so Home
Assistant's tuned answers are preserved while every other repository gains
coverage.

No Syron behaviour here is repo-specific: a concept resolves only if the repo
actually contains matching modules/symbols. If a repo genuinely lacks a concept
(e.g. FastAPI has no caching layer), resolution honestly returns nothing.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

# --------------------------------------------------------------------------
# Lexicon — concept -> matching signals.
#   aliases     : phrases in the user's query that select this concept
#   dir_tokens  : directory segment names that indicate the concept (strong)
#   file_tokens : filename stems that indicate the concept (strongest)
#   symbols     : symbol-name substrings to mine from the symbol index
# All matching is token-level (segment / camelCase aware), never raw substring,
# so "log" matches log.py / logging/ but not "login" or "catalog".
# --------------------------------------------------------------------------
Concept = Dict[str, Tuple[str, ...]]

LEXICON: Dict[str, Concept] = {
    "logging": {
        "aliases": ("logging", "logger", "the logging layer", "log layer", "logs"),
        "dir_tokens": ("logging", "log", "logs"),
        "file_tokens": ("logging", "logger", "log", "logs", "logback", "structlog"),
        "symbols": ("getLogger", "Logger", "setLevel", "addHandler", "createLogger",
                    "ILogger", "LogService", "basicConfig"),
    },
    "events": {
        "aliases": ("events", "event system", "event bus", "the event system", "eventbus",
                    "dispatcher", "event emitter", "emitter", "signals", "pubsub", "pub/sub"),
        "dir_tokens": ("events", "event", "dispatch", "dispatcher", "emitter", "signals", "pubsub"),
        "file_tokens": ("event", "events", "eventbus", "dispatcher", "emitter", "signal",
                        "signals", "pubsub"),
        "symbols": ("EventEmitter", "EventBus", "dispatchEvent", "addEventListener", "emit",
                    "Dispatcher", "Signal", "subscribe", "publish", "async_fire", "async_listen"),
    },
    "background_jobs": {
        "aliases": ("background jobs", "background job", "background tasks", "worker", "workers",
                    "task queue", "job queue", "jobs", "celery", "rq worker", "task runner"),
        "dir_tokens": ("worker", "workers", "jobs", "job", "tasks", "queue", "background", "celery"),
        "file_tokens": ("worker", "workers", "job", "jobs", "task", "tasks", "queue", "background",
                        "celery"),
        "symbols": ("Worker", "Queue", "enqueue", "apply_async", "delay", "BackgroundTasks",
                    "run_in_executor", "JobRunner", "TaskRunner"),
    },
    "scheduling": {
        "aliases": ("scheduling", "scheduler", "schedule", "cron", "timer", "periodic tasks",
                    "interval"),
        "dir_tokens": ("scheduler", "schedule", "scheduling", "cron", "timer", "timers"),
        "file_tokens": ("scheduler", "schedule", "scheduling", "cron", "timer", "interval",
                        "periodic"),
        "symbols": ("Scheduler", "schedule", "setInterval", "setTimeout", "Cron", "Timer",
                    "async_track_time_interval", "every", "add_job"),
    },
    "state_management": {
        "aliases": ("state management", "state", "store", "redux", "state machine", "statemachine",
                    "app state", "state store"),
        "dir_tokens": ("state", "store", "stores", "redux", "reducers", "statemachine"),
        "file_tokens": ("state", "store", "stores", "reducer", "reducers", "statemachine", "redux"),
        "symbols": ("Store", "useState", "createStore", "reducer", "StateMachine", "setState",
                    "Atom", "observable", "writable", "useReducer"),
    },
    "plugins": {
        "aliases": ("plugins", "plugin", "plugin system", "the plugin system", "addons", "addon",
                    "add-ons", "hooks system"),
        "dir_tokens": ("plugin", "plugins", "addon", "addons", "extensions", "hooks"),
        "file_tokens": ("plugin", "plugins", "addon", "addons", "pluginmanager", "registry"),
        "symbols": ("Plugin", "PluginManager", "register_plugin", "load_plugin", "registerPlugin",
                    "Hook", "ExtensionPoint", "Addon", "loadPlugins"),
    },
    "api_layer": {
        "aliases": ("api layer", "the api layer", "api", "endpoints", "endpoint", "rest api",
                    "controllers", "handlers", "resources", "web api"),
        "dir_tokens": ("api", "apis", "endpoints", "controllers", "controller", "handlers",
                       "resources", "rest", "views", "resolvers", "openapi"),
        "file_tokens": ("api", "endpoint", "endpoints", "controller", "handler", "resource",
                        "routes", "router", "views", "openapi"),
        "symbols": ("Router", "APIRouter", "Controller", "endpoint", "RequestHandler", "Resource",
                    "route", "get_route", "add_api_route"),
    },
    # ---- broadened existing concepts (help all repos, not just the 7 zeros) ----
    "authentication": {
        "aliases": ("authentication", "auth", "login", "sign in", "signin", "oauth", "credentials",
                    "identity"),
        "dir_tokens": ("auth", "authentication", "security", "identity", "login", "oauth"),
        "file_tokens": ("auth", "authentication", "security", "login", "oauth", "credentials",
                        "identity", "session"),
        "symbols": ("authenticate", "AuthProvider", "AuthStore", "login", "OAuth", "verify_token",
                    "AuthenticationService", "currentUser"),
    },
    "authorization": {
        "aliases": ("authorization", "access control", "permissions", "rbac", "roles", "acl",
                    "guards"),
        "dir_tokens": ("authz", "authorization", "permissions", "rbac", "acl", "policies", "guards",
                       "roles"),
        "file_tokens": ("authorization", "permission", "permissions", "rbac", "acl", "policy",
                        "policies", "guard", "guards", "roles"),
        "symbols": ("Permission", "authorize", "has_permission", "can", "Policy", "Guard",
                    "RoleGuard", "checkAccess", "CanActivate"),
    },
    "caching": {
        "aliases": ("caching", "cache", "the cache layer", "memoization"),
        "dir_tokens": ("cache", "caching", "caches"),
        "file_tokens": ("cache", "caching", "memoize", "lru"),
        "symbols": ("Cache", "lru_cache", "cache_get", "cache_set", "memoize", "CacheService",
                    "getCache", "TTLCache"),
    },
    "configuration": {
        "aliases": ("configuration", "config", "settings", "the config system", "preferences"),
        "dir_tokens": ("config", "configuration", "conf", "settings", "preferences"),
        "file_tokens": ("config", "configuration", "conf", "settings", "preferences", "options"),
        "symbols": ("Config", "Settings", "getConfig", "load_config", "ConfigurationService",
                    "Preferences", "from_env"),
    },
    "database": {
        "aliases": ("database", "the database layer", "db", "persistence layer", "datastore",
                    "storage"),
        "dir_tokens": ("db", "database", "storage", "store", "persistence", "datastore", "sql",
                       "models", "migrations"),
        "file_tokens": ("db", "database", "storage", "persistence", "datastore", "sqlite", "sql",
                        "connection", "session", "recorder"),
        "symbols": ("Session", "connect", "Database", "Engine", "Storage", "Repository", "execute",
                    "Recorder", "createConnection", "Pool"),
    },
    "persistence": {
        "aliases": ("persistence", "persistence layer", "data access", "repositories", "dao"),
        "dir_tokens": ("persistence", "repositories", "repository", "dao", "store", "storage",
                       "models", "entities"),
        "file_tokens": ("persistence", "repository", "dao", "store", "storage", "entity", "model"),
        "symbols": ("Repository", "save", "persist", "find", "Entity", "DAO", "Store"),
    },
    "routing": {
        "aliases": ("routing", "router", "routes", "url routing", "url dispatch", "the router"),
        "dir_tokens": ("routing", "router", "routes", "urls", "url"),
        "file_tokens": ("routing", "router", "routes", "route", "urls", "url", "urlconf"),
        "symbols": ("Router", "Route", "add_route", "url", "path", "include", "createRouter",
                    "RouterModule"),
    },
    "middleware": {
        "aliases": ("middleware", "middlewares", "the middleware", "interceptors", "filters chain"),
        "dir_tokens": ("middleware", "middlewares", "interceptors"),
        "file_tokens": ("middleware", "middlewares", "interceptor"),
        "symbols": ("Middleware", "process_request", "process_response", "use", "Interceptor",
                    "NextFunction", "dispatch"),
    },
    "messaging": {
        "aliases": ("messaging", "message queue", "message bus", "broker", "mqtt", "amqp", "kafka"),
        "dir_tokens": ("messaging", "messages", "broker", "mqtt", "amqp", "kafka", "rabbit", "queue"),
        "file_tokens": ("messaging", "message", "broker", "mqtt", "amqp", "kafka", "producer",
                        "consumer"),
        "symbols": ("Broker", "publish", "consume", "Producer", "Consumer", "Channel", "send_message"),
    },
    "websockets": {
        "aliases": ("websockets", "websocket", "websocket support", "ws", "realtime sockets"),
        "dir_tokens": ("websocket", "websockets", "ws", "socket", "sockets"),
        "file_tokens": ("websocket", "websockets", "ws", "socket"),
        "symbols": ("WebSocket", "websocket", "WebSocketHandler", "onmessage", "WebSocketAPI",
                    "accept", "send_text"),
    },
    "validation": {
        "aliases": ("validation", "request validation", "validators", "schema validation",
                    "input validation"),
        "dir_tokens": ("validation", "validators", "validator", "schemas", "schema", "params"),
        "file_tokens": ("validation", "validator", "validators", "schema", "schemas", "params",
                        "fields", "forms"),
        "symbols": ("validate", "Validator", "RequestValidationError", "is_valid", "ValidationError",
                    "check", "Schema", "clean"),
    },
    "serialization": {
        "aliases": ("serialization", "serializers", "encoding", "marshalling", "deserialization"),
        "dir_tokens": ("serialization", "serializers", "serializer", "encoders", "encoder",
                       "marshalling", "json"),
        "file_tokens": ("serializer", "serializers", "serialization", "encoder", "encoders",
                        "marshal", "json", "schema"),
        "symbols": ("Serializer", "serialize", "deserialize", "encode", "decode", "to_json",
                    "jsonable_encoder", "Marshal"),
    },
    "extensions": {
        "aliases": ("extensions", "extension", "extension system", "extension host",
                    "the extension host", "extensionhost"),
        "dir_tokens": ("extensions", "extension", "extensionhost", "addons", "plugins",
                       "platform"),
        "file_tokens": ("extension", "extensions", "extensionhost", "extensionpoint"),
        "symbols": ("Extension", "ExtensionHost", "activate", "registerExtension", "ExtensionService"),
    },
    "dependency_injection": {
        "aliases": ("dependency injection", "dependencies", "di container", "inversion of control",
                    "ioc", "providers", "injector"),
        "dir_tokens": ("dependencies", "di", "injection", "providers", "container"),
        "file_tokens": ("dependencies", "dependency", "injector", "provider", "container", "depends"),
        "symbols": ("Depends", "inject", "Injectable", "Provider", "Container", "resolve",
                    "get_dependency", "useFactory"),
    },
    "orm": {
        "aliases": ("the orm", "orm", "object relational mapper", "models layer", "entity model"),
        "dir_tokens": ("orm", "models", "entities", "schema", "db"),
        "file_tokens": ("orm", "model", "models", "entity", "entities", "query", "queryset"),
        "symbols": ("Model", "QuerySet", "Field", "objects", "Entity", "Column", "relationship"),
    },
    "template_engine": {
        "aliases": ("the template engine", "template engine", "templates", "templating", "views"),
        "dir_tokens": ("template", "templates", "templating", "templatetags", "views"),
        "file_tokens": ("template", "templates", "templating", "renderer", "engine"),
        "symbols": ("Template", "render", "Engine", "render_to_string", "compile", "Context"),
    },
    "editor": {
        "aliases": ("the editor", "editor", "text editor", "code editor"),
        "dir_tokens": ("editor", "editors", "codeeditor"),
        "file_tokens": ("editor", "editors", "codeeditor", "texteditor"),
        "symbols": ("Editor", "CodeEditor", "TextModel", "EditorService", "ICodeEditor"),
    },
    "command_registry": {
        "aliases": ("the command registry", "command registry", "commands", "command palette"),
        "dir_tokens": ("commands", "command", "actions"),
        "file_tokens": ("commands", "command", "commandregistry", "commandservice", "actions"),
        "symbols": ("CommandRegistry", "registerCommand", "executeCommand", "ICommandService",
                    "addCommand"),
    },
    "workbench": {
        "aliases": ("workbench", "the workbench", "shell", "ide shell"),
        "dir_tokens": ("workbench", "shell"),
        "file_tokens": ("workbench", "shell"),
        "symbols": ("Workbench", "IWorkbench", "WorkbenchService", "createWorkbench"),
    },
}

# Filler words stripped from a query before alias matching.
_FILLER = {"the", "a", "an", "layer", "system", "support", "module", "subsystem",
           "of", "for", "remove", "removing", "delete", "deleting", "disable",
           "what", "breaks", "if", "i", "we", "this", "repo", "repository"}

# Build alias -> concept (longest alias first so multi-word phrases win).
_ALIASES: List[Tuple[str, str]] = sorted(
    ((alias.lower(), cid) for cid, spec in LEXICON.items() for alias in spec.get("aliases", ())),
    key=lambda kv: -len(kv[0]),
)


def _decamel(s: str) -> str:
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", s)
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", s)
    return s


def _tokens(text: str) -> List[str]:
    return [t for t in re.findall(r"[a-z0-9]+", _decamel(text or "").lower()) if t]


def match_concept(query: str) -> Optional[str]:
    """Map a free-text query to a lexicon concept id (or None)."""
    q = " " + " ".join(t for t in _tokens(query) if t not in _FILLER) + " "
    raw = " " + (query or "").lower().strip() + " "
    for alias, cid in _ALIASES:
        a = " " + alias + " "
        if a in raw or a in q:
            return cid
    return None


def _path_parts(path: str) -> Tuple[List[str], str, Set[str], Set[str]]:
    """Return (dir_segments, file_stem, file_words, dir_words) for a path."""
    p = (path or "").replace("\\", "/").strip().lower()
    segs = [s for s in p.split("/") if s]
    if not segs:
        return [], "", set(), set()
    last = segs[-1]
    file_stem = last.rsplit(".", 1)[0] if "." in last else last
    dir_segs = segs[:-1] if "." in last else segs
    file_words = set(_tokens(file_stem))
    dir_words: Set[str] = set()
    for d in dir_segs:
        dir_words.update(_tokens(d))
    return dir_segs, file_stem, file_words, dir_words


def _token_hit(needle: str, words: Set[str]) -> bool:
    """A token match: exact word, or a strong shared stem (>=4 chars)."""
    if needle in words:
        return True
    for w in words:
        if len(needle) >= 4 and len(w) >= 4 and (w.startswith(needle) or needle.startswith(w)):
            return True
    return False


def score_module_for_concept(path: str, concept: Concept, *, symbol_file: bool,
                             fan_in: int) -> int:
    """Score one module path against a concept. 0 means no signal."""
    dir_segs, file_stem, file_words, dir_words = _path_parts(path)
    if not file_stem:
        return 0
    file_tokens = tuple(concept.get("file_tokens", ()))
    dir_tokens = tuple(concept.get("dir_tokens", ()))
    score = 0
    # Filename is the strongest signal (e.g. routing.py, scheduler.py, logging.py).
    if file_stem in file_tokens:
        score += 120
    elif any(_token_hit(t, file_words) for t in file_tokens):
        score += 55
    # Directory name (e.g. .../security/..., .../events/..., conf/).
    if any(t in dir_segs for t in dir_tokens):
        score += 70
    elif any(_token_hit(t, dir_words) for t in dir_tokens):
        score += 28
    # Mined symbols inside the file.
    if symbol_file:
        score += 60
    if score <= 0:
        return 0
    return score + min(int(fan_in or 0), 25)
