"""扫描缓存管理 - 加速二次扫描"""

import json
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import asdict
from core.scanner import DirectoryStat


CACHE_FILE = Path("scan_cache.json")


def save_scan_cache(stats: List[DirectoryStat], ai_results: Dict[str, Dict] = None) -> None:
    """保存扫描结果到缓存
    
    Args:
        stats: 目录统计信息列表
        ai_results: AI 分析结果字典 {path: {category, summary, confidence}}
    """
    ai_results = ai_results or {}
    
    cache_data = {
        "version": "1.1",  # 升级版本，支持 AI 结果
        "directories": [
            {
                "path": str(stat.path),
                "size_bytes": stat.size_bytes,
                "file_count": stat.file_count,
                "latest_atime": stat.latest_atime,
                "latest_mtime": stat.latest_mtime,
                # AI 分析结果（如果有）
                "ai_category": ai_results.get(str(stat.path), {}).get("category", ""),
                "ai_summary": ai_results.get(str(stat.path), {}).get("summary", ""),
                "ai_confidence": ai_results.get(str(stat.path), {}).get("confidence", 0.0),
            }
            for stat in stats
        ]
    }
    
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass  # 缓存失败不影响主流程


def load_scan_cache() -> List[Dict]:
    """加载缓存的扫描结果"""
    if not CACHE_FILE.exists():
        return []
    
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("directories", [])
    except Exception:
        return []


def verify_cached_directory(cached: Dict) -> Optional[DirectoryStat]:
    """验证缓存的目录是否仍然存在并需要清理
    
    返回:
        - DirectoryStat: 目录仍存在且有问题
        - None: 目录已删除或已清理
    """
    import os
    import stat as stat_module
    
    path = Path(cached["path"])
    
    # 检查目录是否还存在
    if not path.exists() or not path.is_dir():
        return None
    
    try:
        # 重新统计目录信息
        size_bytes = 0
        file_count = 0
        dir_count = 0
        latest_atime = 0.0
        latest_mtime = 0.0
        
        with os.scandir(path) as it:
            for entry in it:
                try:
                    st = entry.stat(follow_symlinks=False)
                    if stat_module.S_ISREG(st.st_mode):
                        file_count += 1
                        size_bytes += st.st_size
                        latest_atime = max(latest_atime, st.st_atime)
                        latest_mtime = max(latest_mtime, st.st_mtime)
                    elif stat_module.S_ISDIR(st.st_mode):
                        dir_count += 1
                except (PermissionError, FileNotFoundError, OSError):
                    continue
        
        # 如果大小明显减少（>50%），说明已被清理
        old_size = cached.get("size_bytes", 0)
        if old_size > 0 and size_bytes < old_size * 0.5:
            return None
        
        # 返回最新的统计信息
        return DirectoryStat(
            path=path,
            size_bytes=size_bytes,
            file_count=file_count,
            dir_count=dir_count,
            latest_atime=latest_atime,
            latest_mtime=latest_mtime,
        )
    except (PermissionError, FileNotFoundError, OSError):
        return None


def get_cached_paths_set() -> set:
    """获取缓存中所有路径的集合（用于全盘扫描时排除）"""
    cached = load_scan_cache()
    return {Path(item["path"]) for item in cached}
