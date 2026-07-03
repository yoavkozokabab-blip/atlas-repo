"""Generate medium_repo and large_repo demo packs (run once during dev/build)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_medium() -> None:
    root = ROOT / "medium_repo"
    _write(root / "README.md", "# Atlas Demo — Medium\n\n~18 modules across four subsystems.\n")
    _write(root / "shared" / "config.py", "APP_NAME = 'medium-demo'\n")
    _write(root / "shared" / "logging.py", "from shared.config import APP_NAME\n\ndef log(msg: str) -> str:\n    return f'{APP_NAME}:{msg}'\n")
    _write(root / "api" / "routes.py", "from services.auth import authenticate\n\ndef list_routes():\n    return authenticate('demo')\n")
    _write(root / "api" / "handlers.py", "from api.routes import list_routes\n\ndef handle():\n    return list_routes()\n")
    _write(root / "services" / "auth.py", "from shared.logging import log\n\ndef authenticate(user: str) -> str:\n    return log(user)\n")
    _write(root / "services" / "billing.py", "from services.auth import authenticate\n\ndef charge(user: str) -> str:\n    return authenticate(user)\n")
    _write(root / "services" / "notify.py", "from shared.logging import log\n\ndef ping():\n    return log('ping')\n")
    _write(root / "ui" / "dashboard.py", "from api.handlers import handle\n\ndef render():\n    return handle()\n")
    _write(root / "ui" / "widgets.py", "from ui.dashboard import render\n\ndef widget():\n    return render()\n")
    for idx in range(1, 9):
        _write(
            root / f"workers" / f"job_{idx}.py",
            "from services.notify import ping\nfrom services.billing import charge\n\n"
            f"def run_job_{idx}():\n    return ping(), charge('user{idx}')\n",
        )


def build_large() -> None:
    root = ROOT / "large_repo"
    _write(root / "README.md", "# Atlas Demo — Large\n\n~40 modules across six subsystems.\n")
    _write(root / "platform" / "kernel.py", "def boot():\n    return 'ok'\n")
    _write(root / "platform" / "scheduler.py", "from platform.kernel import boot\n\ndef schedule():\n    return boot()\n")
    subs = ("voice", "builder", "assistant", "analytics", "storage")
    for sub in subs:
        _write(root / sub / "core.py", f"from platform.scheduler import schedule\n\ndef {sub}_core():\n    return schedule()\n")
        _write(root / sub / "adapter.py", f"from {sub}.core import {sub}_core\n\ndef adapt():\n    return {sub}_core()\n")
        for idx in range(1, 7):
            _write(
                root / sub / f"module_{idx}.py",
                f"from {sub}.adapter import adapt\n\ndef run_{idx}():\n    return adapt()\n",
            )
    _write(root / "gateway" / "entry.py", "from voice.module_1 import run_1 as v\nfrom builder.module_1 import run_1 as b\n\ndef main():\n    return v(), b()\n")


if __name__ == "__main__":
    build_medium()
    build_large()
    print("Demo packs generated.")
