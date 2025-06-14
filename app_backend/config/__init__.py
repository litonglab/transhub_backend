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
if os.path.exists(env_file):
    load_dotenv(env_file)
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ✅ 已加载环境配置文件: {env_file}")
else:
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ⚠️  环境配置文件不存在: {env_file}")
    exit(1)

# 默认配置实例
_default_config = None

# import必须在加载环境变量之后
from .development import DevelopmentConfig
from .production import ProductionConfig

# 配置映射
CONFIG_MAP: Dict[str, Type[Union[DevelopmentConfig, ProductionConfig]]] = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
}


def get_config(env: str = None) -> Union[DevelopmentConfig, ProductionConfig]:
    """
    获取配置对象

    Args:
        env: 环境名称，如果不提供则从环境变量 APP_ENV 读取

    Returns:
        配置对象实例

    Raises:
        ValueError: 当环境名称无效时
    """
    if env is None:
        env = os.getenv('APP_ENV', 'development')

    config_class = CONFIG_MAP.get(env.lower())
    if config_class is None:
        available_envs = ', '.join(CONFIG_MAP.keys())
        raise ValueError(f"无效的环境名称: {env}. 可用环境: {available_envs}")

    return config_class()


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


def get_default_config() -> Union[DevelopmentConfig, ProductionConfig]:
    """获取默认配置实例（单例模式）"""
    global _default_config
    if _default_config is None:
        _default_config = get_config()
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ✅ 当前配置：{get_config_dict()}")
        # 转换为json
        # print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ✅ 当前配置（JSON格式）: {json.dumps(get_config_dict(), indent=2, ensure_ascii=False)}")
    return _default_config


def reset_default_config():
    """重置默认配置实例（主要用于测试）"""
    global _default_config
    _default_config = None
