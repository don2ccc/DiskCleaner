"""AI 代理服务

用于将 DiskCleaner 的分析请求转发给真实的 AI 大模型。

支持的模型：
- OpenAI (gpt-4o-mini, gpt-4o)
- DeepSeek (deepseek-chat, deepseek-coder)
- 豆包 (通过火山引擎)
- Gemini (gemini-pro, gemini-1.5-flash)

使用方法：
1. 双击运行 start_ai_service.bat (Windows) 自动启动
2. 在 DiskCleaner GUI 中配置 AI 服务
3. 所有配置通过 ai_config.json 管理
"""

import os
import json
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

# 从配置文件读取设置
CONFIG_FILE = Path(__file__).parent / "ai_config.json"

def load_config():
    """加载配置文件，如不存在则创建默认配置"""
    if not CONFIG_FILE.exists():
        default_config = {
            "provider": "deepseek",
            "api_key": "",
            "model_name": "",
            "comment": "provider 可选值: openai, deepseek, doubao, gemini"
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(default_config, f, ensure_ascii=False, indent=2)
        return default_config
    
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

config = load_config()
PROVIDER = config.get("provider", "deepseek").lower()
API_KEY = config.get("api_key", "")
MODEL_NAME = config.get("model_name", "")

if not API_KEY:
    print("警告: 未配置 API_KEY，请编辑 ai_config.json 文件")
    print(f"配置文件路径: {CONFIG_FILE}")

app = FastAPI(title="DiskCleaner AI Proxy")


class AnalyzeRequest(BaseModel):
    path: str
    size_bytes: int
    file_count: int
    dir_count: int


class AnalyzeResponse(BaseModel):
    summary: str
    category: str
    confidence: float


def get_ai_client():
    """根据 PROVIDER 返回对应的 AI 客户端"""
    if PROVIDER == "openai":
        from openai import OpenAI
        return OpenAI(api_key=API_KEY), MODEL_NAME or "gpt-4o-mini"
    
    elif PROVIDER == "deepseek":
        from openai import OpenAI
        return OpenAI(
            api_key=API_KEY,
            base_url="https://api.deepseek.com/v1"
        ), MODEL_NAME or "deepseek-chat"
    
    elif PROVIDER == "doubao":
        from openai import OpenAI
        endpoint_id = MODEL_NAME
        if not endpoint_id:
            raise RuntimeError("豆包需要设置 MODEL_NAME 为你的接入点 ID，如 ep-20240101-xxxxx")
        return OpenAI(
            api_key=API_KEY,
            base_url="https://ark.cn-beijing.volces.com/api/v3"
        ), endpoint_id
    
    elif PROVIDER == "gemini":
        import google.generativeai as genai
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel(MODEL_NAME or "gemini-pro")
        return model, None
    
    else:
        raise RuntimeError(f"不支持的 PROVIDER: {PROVIDER}，可选值: openai, deepseek, doubao, gemini")


def build_prompt(req: AnalyzeRequest) -> str:
    """构造分析 prompt"""
    size_gb = req.size_bytes / (1024 ** 3)
    return f"""你是一个 Windows 磁盘清理助手。请分析以下目录的用途和清理建议：

目录路径: {req.path}
目录大小: {size_gb:.2f} GB
文件数量: {req.file_count}
子目录数: {req.dir_count}

请以 JSON 格式返回分析结果，包含以下字段：
- summary: 简短总结这个目录的用途和是否建议清理（50字以内）
- category: 分类标签，从以下选项中选择一个：下载目录、临时缓存、游戏相关、图片相册、视频电影、开发工具、系统备份、未分类
- confidence: 你对这个判断的置信度，0.0-1.0 之间的浮点数

只返回 JSON，不要其他解释。
"""


def call_openai_compatible(client, model: str, prompt: str) -> dict:
    """调用 OpenAI 兼容接口（OpenAI、DeepSeek、豆包）"""
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=200,
    )
    content = response.choices[0].message.content
    # 尝试提取 JSON（有些模型可能返回带 markdown 包裹的内容）
    import json
    import re
    json_match = re.search(r'\{.*\}', content, re.DOTALL)
    if json_match:
        return json.loads(json_match.group())
    return json.loads(content)


def call_gemini(model, prompt: str) -> dict:
    """调用 Gemini 接口"""
    response = model.generate_content(prompt)
    import json
    import re
    content = response.text
    json_match = re.search(r'\{.*\}', content, re.DOTALL)
    if json_match:
        return json.loads(json_match.group())
    return json.loads(content)


@app.post("/analyze-path", response_model=AnalyzeResponse)
def analyze_path(req: AnalyzeRequest) -> AnalyzeResponse:
    """分析目录用途"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        client, model = get_ai_client()
        prompt = build_prompt(req)
        
        logger.info(f"开始分析: {req.path} ({req.size_bytes / (1024**3):.2f} GB)")
        
        if PROVIDER == "gemini":
            result = call_gemini(client, prompt)
        else:
            result = call_openai_compatible(client, model, prompt)
        
        logger.info(f"分析成功: {result.get('category', 'N/A')} - {result.get('confidence', 0):.0%}")
        
        return AnalyzeResponse(
            summary=result.get("summary", "无法分析"),
            category=result.get("category", "未分类"),
            confidence=float(result.get("confidence", 0.5)),
        )
    except Exception as e:
        logger.error(f"分析失败: {str(e)}")
        logger.exception("详细堆栈:")
        raise HTTPException(status_code=500, detail=f"AI 调用失败: {str(e)}")


@app.get("/health")
def health_check():
    """健康检查"""
    return {"status": "ok", "provider": PROVIDER, "model": MODEL_NAME or "default"}


if __name__ == "__main__":
    import logging
    from pathlib import Path
    
    # 设置日志输出到文件
    log_file = Path(__file__).parent / "ai_service.log"
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger(__name__)
    
    if not API_KEY:
        logger.error("配置错误: 未设置 API_KEY")
        logger.error(f"请编辑配置文件: {CONFIG_FILE}")
        import sys
        sys.exit(1)
    else:
        logger.info(f"AI 服务启动 - Provider: {PROVIDER}")
        logger.info(f"API Key 长度: {len(API_KEY)} 字符")
        logger.info(f"API Key 后缀: ...{API_KEY[-8:] if len(API_KEY) >= 8 else API_KEY}")
        logger.info(f"Model: {MODEL_NAME or 'default'}")
        
        try:
            # 验证配置
            logger.info("验证 AI 客户端配置...")
            client, model = get_ai_client()
            logger.info("✅ AI 客户端配置成功")
            
            # 启动服务 - 使用冷门端口 10089
            logger.info("启动 HTTP 服务器 (0.0.0.0:10089)...")
            uvicorn.run(app, host="0.0.0.0", port=10089, log_level="info")
        except Exception as e:
            logger.error(f"❗ 服务启动失败: {e}")
            logger.exception("详细错误:")
            import sys
            sys.exit(1)
