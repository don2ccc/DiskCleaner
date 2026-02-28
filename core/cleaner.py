from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

try:
    from send2trash import send2trash
    HAS_SEND2TRASH = True
except ImportError:  # pragma: no cover - 依赖缺失时的兜底
    send2trash = None  # type: ignore[assignment]
    HAS_SEND2TRASH = False


@dataclass
class DeleteOptions:
    use_trash: bool = True


def delete_directory(path: Path, options: DeleteOptions | None = None) -> None:
    """删除（或移入回收站）指定目录。

    - 默认使用回收站（更安全）。
    - 如需直接删除，可将 options.use_trash 设为 False。
    """
    if options is None:
        options = DeleteOptions()

    resolved = path.resolve()
    if not resolved.exists():
        return

    if options.use_trash:
        if not HAS_SEND2TRASH:
            raise RuntimeError(
                "需要 send2trash 库来使用回收站删除，请先执行: pip install send2trash",
            )
        send2trash(str(resolved))
    else:
        # 直接删除，谨慎使用
        shutil.rmtree(resolved, ignore_errors=False)


def delete_directories(paths: Iterable[Path], options: DeleteOptions | None = None) -> None:
    for p in paths:
        delete_directory(p, options)
