from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .scanner import DirectoryStat

try:
    import requests
except ImportError:  # pragma: no cover - 未安装 requests 时退化为本地启发式
    requests = None  # type: ignore[assignment]


@dataclass
class AiAnalysisOptions:
    # 是否启用 AI 分析
    enable_ai: bool = False
    # 远程 AI 服务配置（例如你的网关地址和密钥）
    api_base_url: Optional[str] = None
    api_key: Optional[str] = None


@dataclass
class AiAnalysisResult:
    summary: str
    category: str
    confidence: float
    error: str = ""  # 新增：错误信息，空字符串表示成功


class AiAnalyzer:
    """AI 分析器：根据目录统计信息给出用途猜测和清理建议等级。

    说明：
    - 优先尝试调用你配置的外部 AI 服务（HTTP 接口）。
    - 如果未启用或调用失败，则退化为本地启发式规则。
    """

    def _fallback_heuristic(self, stat: DirectoryStat) -> AiAnalysisResult:
        """本地启发式规则，用于在外部 AI 不可用时兜底。"""
        path_str = str(stat.path).lower()

        if any(x in path_str for x in ("\\downloads", "/downloads")):
            category = "下载目录"
        elif any(x in path_str for x in ("temp", "tmp", "cache")):
            category = "临时/缓存"
        elif any(x in path_str for x in ("steam", "epic", "game")):
            category = "游戏相关"
        elif any(x in path_str for x in ("pictures", "photos", "images")):
            category = "图片/相册"
        elif any(x in path_str for x in ("videos", "movie", "film")):
            category = "视频/电影"
        else:
            category = "未分类/通用目录"

        if category in {"下载目录", "临时/缓存"}:
            confidence = 0.8
        elif category in {"游戏相关", "图片/相册", "视频/电影"}:
            confidence = 0.6
        else:
            confidence = 0.4

        summary = f"推测类型: {category}，大约 {stat.size_bytes / (1024**3):.2f} GB"
        return AiAnalysisResult(summary=summary, category=category, confidence=confidence)

    def analyze_path(self, stat: DirectoryStat, options: AiAnalysisOptions) -> AiAnalysisResult:
        # 未启用 AI 或未配置远程地址 -> 本地启发式
        if not options.enable_ai or not options.api_base_url or requests is None:
            return self._fallback_heuristic(stat)

        # 调用外部 AI 服务
        url = options.api_base_url.rstrip("/") + "/analyze-path"
        payload = {
            "path": str(stat.path),
            "size_bytes": stat.size_bytes,
            "file_count": stat.file_count,
            "dir_count": stat.dir_count,
        }
        headers = {"Content-Type": "application/json"}
        if options.api_key:
            headers["Authorization"] = f"Bearer {options.api_key}"

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=20)
            resp.raise_for_status()
            data = resp.json()

            summary = data.get("summary")
            category = data.get("category")
            confidence = float(data.get("confidence", 0.5))
            if not summary or not category:
                # 外部返回不完整，退回本地规则
                result = self._fallback_heuristic(stat)
                result.error = "AI 返回格式不完整，使用本地规则"
                return result

            return AiAnalysisResult(summary=summary, category=category, confidence=confidence)
        except requests.exceptions.Timeout:
            result = self._fallback_heuristic(stat)
            result.error = f"AI 服务超时 (URL: {url})"
            return result
        except requests.exceptions.ConnectionError as e:
            result = self._fallback_heuristic(stat)
            result.error = f"无法连接 AI 服务 ({url}): {str(e)[:50]}"
            return result
        except requests.exceptions.HTTPError as e:
            result = self._fallback_heuristic(stat)
            if e.response.status_code == 401:
                result.error = "API Key 鉴权失败 (401)"
            elif e.response.status_code == 500:
                # 尝试读取响应体
                try:
                    error_detail = e.response.text[:100]
                    result.error = f"AI 服务内部错误 (500): {error_detail}"
                except:
                    result.error = "AI 服务内部错误 (500)"
            else:
                result.error = f"HTTP {e.response.status_code}: {e.response.text[:50]}"
            return result
        except Exception as e:
            result = self._fallback_heuristic(stat)
            result.error = f"未知错误: {str(e)[:100]}"
            return result
