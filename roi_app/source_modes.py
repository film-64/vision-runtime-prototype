from __future__ import annotations


MODE_FRAME = "frame"
MODE_ONLINE = "Online"
MODE_OFFLINE = "Offline"
MODE_REPLAY = "Replay"

SOURCE_MODE_CHOICES = [MODE_FRAME, MODE_ONLINE, MODE_OFFLINE, MODE_REPLAY]


def source_mode_or_default(value: object, *, default: str = MODE_FRAME) -> str:
    text = str(value or "").strip()
    if not text:
        return default
    return text


def is_frame_source_mode(value: object) -> bool:
    return source_mode_or_default(value) == MODE_FRAME


def is_online_source_mode(value: object) -> bool:
    return source_mode_or_default(value) == MODE_ONLINE


def is_offline_source_mode(value: object) -> bool:
    return source_mode_or_default(value) == MODE_OFFLINE


def is_replay_source_mode(value: object) -> bool:
    return source_mode_or_default(value) == MODE_REPLAY
