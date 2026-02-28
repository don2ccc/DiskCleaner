from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum, auto
from typing import Generator, Iterable

from .scanner import DirectoryStat


class CleanPriority(Enum):
    IGNORE = auto()
    NORMAL = auto()
    HIGH = auto()


@dataclass
class RuleOptions:
    high_priority_size_bytes: int
    high_priority_days: int
    normal_priority_size_bytes: int
    normal_priority_days: int


@dataclass
class Candidate:
    directory: DirectoryStat
    priority: CleanPriority


def evaluate_candidates(stats: Iterable[DirectoryStat], options: RuleOptions) -> Generator[Candidate, None, None]:
    """根据时间 + 体积规则评估清理优先级。"""
    now = datetime.now(timezone.utc)

    for s in stats:
        # 有些目录可能没有有效时间信息
        if s.latest_atime <= 0 and s.latest_mtime <= 0:
            priority = CleanPriority.IGNORE
        else:
            latest_ts = max(s.latest_atime, s.latest_mtime)
            last_dt = datetime.fromtimestamp(latest_ts, tz=timezone.utc)
            delta: timedelta = now - last_dt

            if s.size_bytes >= options.high_priority_size_bytes and delta.days >= options.high_priority_days:
                priority = CleanPriority.HIGH
            elif s.size_bytes >= options.normal_priority_size_bytes and delta.days >= options.normal_priority_days:
                priority = CleanPriority.NORMAL
            else:
                priority = CleanPriority.IGNORE

        yield Candidate(directory=s, priority=priority)
