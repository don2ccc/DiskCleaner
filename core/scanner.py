from __future__ import annotations

import os
import stat
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Generator, Iterable, Set


@dataclass
class DirectoryStat:
    path: Path
    size_bytes: int
    file_count: int
    dir_count: int
    latest_atime: float
    latest_mtime: float


def iter_subdirectories(root: Path) -> Iterable[Path]:
    """广度优先遍历 root 下的所有目录（包括 root 本身）。"""
    queue = [root]
    while queue:
        current = queue.pop(0)
        yield current
        try:
            for entry in current.iterdir():
                if entry.is_dir():
                    queue.append(entry)
        except (PermissionError, FileNotFoundError):
            # 无权限或在扫描过程中被删除，直接跳过
            continue


def scan_directories(root: Path, excluded_roots: Set[Path] | None = None) -> Generator[DirectoryStat, None, None]:
    """扫描目录树，按目录聚合统计信息。

    - root: 起始根目录
    - excluded_roots: 需要排除的顶层目录集合（子树整体跳过）
    """
    if excluded_roots is None:
        excluded_roots = set()

    # 归一化排除路径
    excluded_roots = {p.resolve() for p in excluded_roots}
    root = root.resolve()

    for directory in iter_subdirectories(root):
        # 判断是否被排除（若某个排除目录是当前目录的前缀，则整棵子树跳过）
        resolved = directory.resolve()
        if any(str(resolved).startswith(str(ex)) for ex in excluded_roots):
            continue

        size_bytes = 0
        file_count = 0
        dir_count = 0
        latest_atime = 0.0
        latest_mtime = 0.0

        try:
            with os.scandir(resolved) as it:
                for entry in it:
                    try:
                        st = entry.stat(follow_symlinks=False)
                    except (PermissionError, FileNotFoundError, OSError):
                        continue

                    if stat.S_ISDIR(st.st_mode):
                        dir_count += 1
                    elif stat.S_ISREG(st.st_mode):
                        file_count += 1
                        size_bytes += st.st_size

                    latest_atime = max(latest_atime, st.st_atime)
                    latest_mtime = max(latest_mtime, st.st_mtime)
        except (PermissionError, FileNotFoundError, NotADirectoryError, OSError):
            continue

        yield DirectoryStat(
            path=resolved,
            size_bytes=size_bytes,
            file_count=file_count,
            dir_count=dir_count,
            latest_atime=latest_atime,
            latest_mtime=latest_mtime,
        )
