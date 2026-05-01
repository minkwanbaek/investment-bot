#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import urlopen


@dataclass
class NotifyState:
    last_health: str = "unknown"
    last_warning_key: str = ""
    last_sent_at: str | None = None
    recovery_sent_for: str | None = None

    @classmethod
    def load(cls, path: Path) -> "NotifyState":
        if not path.exists():
            return cls()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return cls()
        return cls(
            last_health=payload.get("last_health", "unknown"),
            last_warning_key=payload.get("last_warning_key", ""),
            last_sent_at=payload.get("last_sent_at"),
            recovery_sent_for=payload.get("recovery_sent_for"),
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.__dict__, ensure_ascii=False, indent=2), encoding="utf-8")


def fetch_status(base_url: str) -> dict:
    with urlopen(f"{base_url.rstrip('/')}/auto-trade/status", timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def build_warning_key(status: dict) -> str:
    watchdog = status.get("watchdog", {}) or {}
    warnings = sorted((watchdog.get("warnings") or []))
    return f"{watchdog.get('health','unknown')}|{'/'.join(warnings)}"


def should_send_warning(state: NotifyState, warning_key: str, repeat_minutes: int) -> bool:
    if warning_key != state.last_warning_key:
        return True
    if not state.last_sent_at:
        return True
    try:
        last_sent = datetime.fromisoformat(state.last_sent_at)
    except Exception:
        return True
    return datetime.now(timezone.utc) >= last_sent + timedelta(minutes=repeat_minutes)


def send_message(channel: str, target: str, message: str, dry_run: bool) -> None:
    cmd = [
        "openclaw",
        "message",
        "send",
        "--channel",
        channel,
        "--target",
        target,
        "--message",
        message,
    ]
    if dry_run:
        print("DRY_RUN:", " ".join(cmd))
        return
    subprocess.run(cmd, check=True)


def warning_message(status: dict) -> str:
    watchdog = status.get("watchdog", {}) or {}
    profile = status.get("profile", {}) or {}
    warnings = ", ".join(watchdog.get("warnings") or []) or "unknown"
    selected = profile.get("last_selected_symbols") or []
    selected_preview = ", ".join(selected[:5]) if selected else "none"
    return (
        f"auto-trade watchdog {watchdog.get('health','warning')}\n"
        f"warnings: {warnings}\n"
        f"last_submitted_at: {status.get('last_submitted_at')}\n"
        f"consecutive_skip_count: {status.get('consecutive_skip_count')}\n"
        f"consecutive_zero_evaluated_count: {status.get('consecutive_zero_evaluated_count')}\n"
        f"minutes_since_last_nonempty_batch: {watchdog.get('minutes_since_last_nonempty_batch')}\n"
        f"last_selected_symbols: {selected_preview}"
    )


def recovery_message(status: dict) -> str:
    profile = status.get("profile", {}) or {}
    selected = profile.get("last_selected_symbols") or []
    selected_preview = ", ".join(selected[:5]) if selected else "none"
    return (
        "auto-trade watchdog recovered\n"
        f"last_submitted_at: {status.get('last_submitted_at')}\n"
        f"last_selected_symbols: {selected_preview}"
    )


def run_once(args: argparse.Namespace, state: NotifyState, state_path: Path) -> None:
    status = fetch_status(args.base_url)
    watchdog = status.get("watchdog", {}) or {}
    health = watchdog.get("health", "unknown")
    warning_key = build_warning_key(status)

    if health in {"warning", "degraded"}:
        if should_send_warning(state, warning_key, args.repeat_minutes):
            send_message(args.channel, args.target, warning_message(status), args.dry_run)
            state.last_sent_at = datetime.now(timezone.utc).isoformat()
            state.recovery_sent_for = None
        state.last_health = health
        state.last_warning_key = warning_key
        state.save(state_path)
        return

    if state.last_health in {"warning", "degraded"} and state.recovery_sent_for != state.last_warning_key:
        send_message(args.channel, args.target, recovery_message(status), args.dry_run)
        state.recovery_sent_for = state.last_warning_key
        state.last_sent_at = datetime.now(timezone.utc).isoformat()

    state.last_health = health
    state.last_warning_key = warning_key
    state.save(state_path)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Poll auto-trade watchdog status and send chat alerts")
    p.add_argument("--base-url", default="http://127.0.0.1:8000")
    p.add_argument("--channel", required=True)
    p.add_argument("--target", required=True)
    p.add_argument("--poll-seconds", type=int, default=60)
    p.add_argument("--repeat-minutes", type=int, default=15)
    p.add_argument("--state-file", default="ops/watchdog/auto_trade_watchdog_state.json")
    p.add_argument("--once", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    state_path = Path(args.state_file)
    state = NotifyState.load(state_path)
    if args.once:
        run_once(args, state, state_path)
        return 0
    while True:
        try:
            run_once(args, state, state_path)
            state = NotifyState.load(state_path)
        except Exception as exc:
            print(f"watchdog notifier error: {exc}", file=sys.stderr)
        time.sleep(max(args.poll_seconds, 15))


if __name__ == "__main__":
    raise SystemExit(main())
