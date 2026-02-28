"""智能清理规则 - 识别常见的空间占用大户"""

from pathlib import Path
from typing import Optional
import os


class PathCategory:
    """路径分类与清理建议"""
    
    # 社交软件缓存路径模式
    SOCIAL_PATTERNS = {
        "WeChat": {
            "paths": ["WeChat Files"],
            "name": "微信缓存",
            "safe_delete": False,
            "guide": "请打开微信 > 设置 > 文件管理 > 清理聊天记录，不要手动删除此文件夹"
        },
        "QQ": {
            "paths": ["Tencent\\QQ", "QQ"],
            "name": "QQ缓存",
            "safe_delete": False,
            "guide": "请打开QQ > 设置 > 文件管理 > 清理缓存文件"
        },
        "DingTalk": {
            "paths": ["DingTalk"],
            "name": "钉钉缓存",
            "safe_delete": False,
            "guide": "请打开钉钉 > 设置 > 通用 > 清理缓存"
        }
    }
    
    # 开发工具缓存
    DEV_PATTERNS = {
        "pip_cache": {
            "paths": ["pip\\cache", "AppData\\Local\\pip"],
            "name": "Pip缓存",
            "safe_delete": True,
            "guide": "可安全删除，或运行命令：pip cache purge"
        },
        "npm_cache": {
            "paths": ["npm-cache", "AppData\\Roaming\\npm-cache"],
            "name": "NPM缓存",
            "safe_delete": True,
            "guide": "可安全删除，或运行命令：npm cache clean --force"
        },
        "nvidia_driver": {
            "paths": ["ProgramData\\NVIDIA Corporation\\NetService"],
            "name": "NVIDIA驱动残留",
            "safe_delete": True,
            "guide": "旧驱动安装包备份，可安全删除"
        }
    }
    
    # 系统临时文件
    TEMP_PATTERNS = {
        "user_temp": {
            "paths": ["AppData\\Local\\Temp"],
            "name": "临时文件",
            "safe_delete": True,
            "guide": "系统临时文件，可安全删除（删不掉的跳过即可）"
        },
        "windows_temp": {
            "paths": ["Windows\\Temp"],
            "name": "系统临时文件",
            "safe_delete": True,
            "guide": "需要管理员权限，建议使用系统磁盘清理工具"
        }
    }
    
    # 浏览器缓存
    BROWSER_PATTERNS = {
        "chrome": {
            "paths": ["AppData\\Local\\Google\\Chrome\\User Data\\Default\\Cache"],
            "name": "Chrome缓存",
            "safe_delete": True,
            "guide": "浏览器缓存，可安全删除"
        },
        "edge": {
            "paths": ["AppData\\Local\\Microsoft\\Edge\\User Data\\Default\\Cache"],
            "name": "Edge缓存",
            "safe_delete": True,
            "guide": "浏览器缓存，可安全删除"
        }
    }
    
    @classmethod
    def categorize_path(cls, path: Path) -> Optional[dict]:
        """识别路径属于哪个类别
        
        返回: {
            "category": "社交软件" | "开发工具" | "临时文件" | "浏览器缓存",
            "name": "微信缓存",
            "safe_delete": True/False,
            "guide": "清理建议文本"
        }
        """
        path_str = str(path).lower()
        
        # 检查社交软件
        for key, info in cls.SOCIAL_PATTERNS.items():
            if any(pattern.lower() in path_str for pattern in info["paths"]):
                return {
                    "category": "社交软件",
                    "name": info["name"],
                    "safe_delete": info["safe_delete"],
                    "guide": info["guide"]
                }
        
        # 检查开发工具
        for key, info in cls.DEV_PATTERNS.items():
            if any(pattern.lower() in path_str for pattern in info["paths"]):
                return {
                    "category": "开发工具",
                    "name": info["name"],
                    "safe_delete": info["safe_delete"],
                    "guide": info["guide"]
                }
        
        # 检查临时文件
        for key, info in cls.TEMP_PATTERNS.items():
            if any(pattern.lower() in path_str for pattern in info["paths"]):
                return {
                    "category": "临时文件",
                    "name": info["name"],
                    "safe_delete": info["safe_delete"],
                    "guide": info["guide"]
                }
        
        # 检查浏览器缓存
        for key, info in cls.BROWSER_PATTERNS.items():
            if any(pattern.lower() in path_str for pattern in info["paths"]):
                return {
                    "category": "浏览器缓存",
                    "name": info["name"],
                    "safe_delete": info["safe_delete"],
                    "guide": info["guide"]
                }
        
        return None


def get_quick_clean_targets() -> list:
    """获取一键清理的目标路径列表
    
    返回可安全快速清理的路径（临时文件、缓存等）
    """
    user_profile = Path(os.environ.get("USERPROFILE", "C:/Users/Default"))
    
    targets = []
    
    # 用户临时文件
    temp_path = user_profile / "AppData" / "Local" / "Temp"
    if temp_path.exists():
        targets.append({
            "path": temp_path,
            "name": "用户临时文件",
            "reason": "系统和应用的临时文件"
        })
    
    # Pip 缓存（如果存在）
    pip_cache = user_profile / "AppData" / "Local" / "pip" / "cache"
    if pip_cache.exists():
        targets.append({
            "path": pip_cache,
            "name": "Python Pip 缓存",
            "reason": "Python 包安装缓存"
        })
    
    # NPM 缓存
    npm_cache = user_profile / "AppData" / "Roaming" / "npm-cache"
    if npm_cache.exists():
        targets.append({
            "path": npm_cache,
            "name": "NPM 缓存",
            "reason": "Node.js 包安装缓存"
        })
    
    # Chrome 缓存
    chrome_cache = user_profile / "AppData" / "Local" / "Google" / "Chrome" / "User Data" / "Default" / "Cache"
    if chrome_cache.exists():
        targets.append({
            "path": chrome_cache,
            "name": "Chrome 浏览器缓存",
            "reason": "网页缓存文件"
        })
    
    # Edge 缓存
    edge_cache = user_profile / "AppData" / "Local" / "Microsoft" / "Edge" / "User Data" / "Default" / "Cache"
    if edge_cache.exists():
        targets.append({
            "path": edge_cache,
            "name": "Edge 浏览器缓存",
            "reason": "网页缓存文件"
        })
    
    return targets


def get_system_clean_guide() -> str:
    """返回系统磁盘清理工具的使用指引"""
    return """Windows 系统自带磁盘清理（最安全）：

1. 右键点击 C 盘 > 属性 > 磁盘清理
2. 点击"清理系统文件"按钮（重要！）
3. 勾选：
   - Windows 更新清理
   - 传递优化文件
   - 设备驱动程序软件包
   - 临时文件

预计可释放：2GB ~ 20GB
"""


def is_critical_system_path(path: Path) -> bool:
    """判断是否为关键系统路径（绝对不能删）"""
    path_str = str(path).lower()
    
    critical_patterns = [
        "\\windows\\",
        "\\program files\\",
        "\\program files (x86)\\",
        "\\programdata\\",
        "\\users\\public\\",
        "\\system32\\",
        "\\syswow64\\",
        "site-packages",  # Python 库
    ]
    
    return any(pattern in path_str for pattern in critical_patterns)
