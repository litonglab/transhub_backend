"""
配置模块 - 支持多环境配置管理

使用方法:
    from app_backend.config import get_default_config
    config = get_default_config()
"""
import os
from datetime import datetime
from typing import Type, Dict, Any, Union

from dotenv import load_dotenv

app_env = os.getenv('APP_ENV', 'development')
env_file = f'.env.{app_env}'


# 由于循环导入，此模块不允许使用logger
def _print_config_log(message: str):
    """
    打印配置加载日志
    """
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {message}")


if os.path.exists(env_file):
    load_dotenv(env_file)
    _print_config_log(f"✅ 已加载环境配置文件: {env_file}")
else:
    _print_config_log(f"⚠️ 环境配置文件不存在: {env_file}, 请检查是否已正确配置, 完整路径: {os.path.abspath(env_file)}")
    exit(1)

# 默认配置实例
_default_config = None


from .base import BaseConfig

def get_config(env: str = None) -> BaseConfig:
    env = (env or os.getenv("APP_ENV", "development")).lower()

    if env == "development":
        from .development import DevelopmentConfig
        return DevelopmentConfig()

    if env == "production":
        from .production import ProductionConfig
        return ProductionConfig()

    raise ValueError(f"无效的环境名称: {env}")


def get_config_dict(env: str = None) -> Dict[str, Any]:
    """
    获取配置字典（向后兼容）
    
    Args:
        env: 环境名称
        
    Returns:
        配置字典
    """
    config = get_config(env)
    return config.to_dict()


def get_default_config() -> BaseConfig:
    """获取默认配置实例（单例模式）"""
    global _default_config
    if _default_config is None:
        _default_config = get_config()
        _print_config_log(f"✅ 当前配置：{get_config_dict()}")
        # 转换为json
        # _print_config_log(f"✅ 当前配置（JSON格式）: {json.dumps(get_config_dict(), indent=2, ensure_ascii=False)}")
    return _default_config


def reset_default_config():
    """重置默认配置实例（主要用于测试）"""
    global _default_config
    _default_config = None
