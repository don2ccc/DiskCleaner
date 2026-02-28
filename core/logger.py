"""日志记录模块 - 用于记录 DiskCleaner 的所有关键交互和操作"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime
import traceback


def setup_logger(name: str = "DiskCleaner") -> logging.Logger:
    """设置日志记录器
    
    - 日志文件：disk-cleaner.log
    - 最大大小：20MB
    - 备份数量：3 个（总共最多 60MB）
    - 格式：时间戳 | 级别 | 消息
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # 避免重复添加 handler
    if logger.handlers:
        return logger
    
    # 日志文件路径
    log_file = Path("disk-cleaner.log")
    
    # 创建 RotatingFileHandler (20MB, 保留3个备份)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=20 * 1024 * 1024,  # 20MB
        backupCount=3,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    
    # 设置日志格式
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    
    return logger


# 全局日志实例
logger = setup_logger()


def log_startup():
    """记录应用启动"""
    logger.info("=" * 80)
    logger.info("DiskCleaner 启动")
    logger.info("=" * 80)


def log_shutdown():
    """记录应用退出"""
    logger.info("DiskCleaner 退出")
    logger.info("=" * 80 + "\n")


def log_scan_start(root: str):
    """记录扫描开始"""
    logger.info(f"开始扫描: {root}")


def log_scan_complete(count: int, duration: float):
    """记录扫描完成"""
    logger.info(f"扫描完成: 已扫描 {count} 个目录，耗时 {duration:.2f} 秒")


def log_scan_cancelled():
    """记录扫描取消"""
    logger.warning("用户取消扫描")


def log_rule_evaluation(high_count: int, normal_count: int, ignored_count: int):
    """记录规则评估结果"""
    logger.info(f"规则评估完成: 高优先级 {high_count} 项, 普通 {normal_count} 项, 忽略 {ignored_count} 项")


def log_ai_analysis_start(count: int):
    """记录 AI 分析开始"""
    logger.info(f"开始 AI 分析: {count} 个目录")


def log_ai_analysis_complete(success_count: int, error_count: int):
    """记录 AI 分析完成"""
    if error_count > 0:
        logger.warning(f"AI 分析完成: 成功 {success_count} 项, 失败 {error_count} 项 (使用本地规则)")
    else:
        logger.info(f"AI 分析完成: 成功分析 {success_count} 项")


def log_ai_error(path: str, error_msg: str):
    """记录 AI 分析错误"""
    logger.error(f"AI 分析失败 [{path}]: {error_msg}")


def log_ai_service_start():
    """记录 AI 服务启动"""
    logger.info("尝试启动 AI 代理服务")


def log_ai_service_status(running: bool, provider: str = None):
    """记录 AI 服务状态"""
    if running:
        logger.info(f"AI 服务运行中: {provider}")
    else:
        logger.warning("AI 服务未运行")


def log_ai_config_save(provider: str, has_api_key: bool):
    """记录 AI 配置保存"""
    if has_api_key:
        logger.info(f"AI 配置已保存: provider={provider}, api_key=已配置")
    else:
        logger.warning(f"AI 配置保存失败: 缺少 API Key")


def log_delete_operation(paths: list, use_trash: bool, count: int):
    """记录删除操作"""
    mode = "回收站" if use_trash else "直接删除"
    logger.info(f"执行删除操作 ({mode}): {count} 个目录")
    for path in paths[:10]:  # 最多记录前10个
        logger.info(f"  - {path}")
    if len(paths) > 10:
        logger.info(f"  ... 共 {len(paths)} 个目录")


def log_delete_success(path: str, use_trash: bool):
    """记录删除成功"""
    mode = "回收站" if use_trash else "直接删除"
    logger.info(f"删除成功 ({mode}): {path}")


def log_delete_error(path: str, error: Exception):
    """记录删除失败"""
    logger.error(f"删除失败 [{path}]: {error}")


def log_settings_change(setting_name: str, old_value, new_value):
    """记录设置变更"""
    logger.info(f"设置变更 [{setting_name}]: {old_value} -> {new_value}")


def log_error(operation: str, error: Exception):
    """记录通用错误"""
    logger.error(f"错误 [{operation}]: {error}")
    logger.debug(traceback.format_exc())


def log_user_action(action: str, details: str = None):
    """记录用户操作"""
    if details:
        logger.info(f"用户操作: {action} | {details}")
    else:
        logger.info(f"用户操作: {action}")
