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


def _translate_warning_codes(warnings: list[str]) -> str:
    mapping = {
        "zero_evaluated_symbols_streak": "평가 심볼 0개 상태가 연속 발생",
        "consecutive_skip_streak": "연속 스킵 누적",
        "no_submission_since_start": "시작 후 주문 제출 없음",
        "no_nonempty_batch_recently": "최근 유효 배치 없음",
    }
    return ", ".join(mapping.get(w, w) for w in warnings) if warnings else "원인 미상"


def warning_message(status: dict) -> str:
    watchdog = status.get("watchdog", {}) or {}
    profile = status.get("profile", {}) or {}
    warnings = list(watchdog.get("warnings") or [])
    selected = profile.get("last_selected_symbols") or []
    selected_preview = ", ".join(selected[:5]) if selected else "없음"
    health_map = {"warning": "경고", "degraded": "심각", "ok": "정상"}
    return (
        f"자동매매 watchdog {health_map.get(watchdog.get('health', 'warning'), watchdog.get('health', 'warning'))}\n"
        f"사유: {_translate_warning_codes(warnings)}\n"
        f"마지막 주문 시각: {status.get('last_submitted_at') or '없음'}\n"
        f"연속 스킵: {status.get('consecutive_skip_count')}회\n"
        f"연속 0심볼 평가: {status.get('consecutive_zero_evaluated_count')}회\n"
        f"최근 유효 배치 경과: {watchdog.get('minutes_since_last_nonempty_batch')}분\n"
        f"최근 확인 심볼: {selected_preview}"
    )


def _should_notify_for_status(status: dict) -> bool:
    watchdog = status.get("watchdog", {}) or {}
    warnings = set(watchdog.get("warnings") or [])
    zero_eval_count = int(status.get("consecutive_zero_evaluated_count") or 0)
    minutes_since_nonempty = watchdog.get("minutes_since_last_nonempty_batch")

    # Ignore normal no-signal periods and short-lived selector empties.
    # Notify only when the selector-empty condition persists long enough to look operationally unhealthy.
    if "zero_evaluated_symbols_streak" in warnings and zero_eval_count >= 5:
        return True
    if "no_nonempty_batch_recently" in warnings and zero_eval_count >= 3:
        return True
    if minutes_since_nonempty is not None and float(minutes_since_nonempty) >= 30 and zero_eval_count >= 2:
        return True
    return False


def run_once(args: argparse.Namespace, state: NotifyState, state_path: Path) -> None:
    status = fetch_status(args.base_url)
    watchdog = status.get("watchdog", {}) or {}
    health = watchdog.get("health", "unknown")
    warning_key = build_warning_key(status)

    if health in {"warning", "degraded"} and _should_notify_for_status(status):
        if should_send_warning(state, warning_key, args.repeat_minutes):
            send_message(args.channel, args.target, warning_message(status), args.dry_run)
            state.last_sent_at = datetime.now(timezone.utc).isoformat()
            state.recovery_sent_for = None
        state.last_health = health
        state.last_warning_key = warning_key
        state.save(state_path)
        return

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
