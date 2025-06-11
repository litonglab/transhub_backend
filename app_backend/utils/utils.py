import logging
import os
import socket
import threading
import random
import string
from logging.config import dictConfig

# noinspection PyUnresolvedReferences
import concurrent_log_handler

from app_backend import get_default_config

# 用于管理分配的端口
allocated_ports = set()
logger = logging.getLogger(__name__)


def _acquire_redis_lock(port, redis_client):
    lock_name = f"port_lock_{port}"
    logger.debug(f"Attempting to acquire Redis lock for port {port}")
    result = redis_client.set(lock_name, "locked", nx=True, ex=600)  # 设置过期时间为60秒
    if result:
        logger.debug(f"Successfully acquired Redis lock for port {port}")
    else:
        logger.error(f"Failed to acquire Redis lock for port {port}")
    return result


def _release_redis_lock(port, redis_client):
    lock_name = f"port_lock_{port}"
    logger.debug(f"Releasing Redis lock for port {port}")
    redis_client.delete(lock_name)
    logger.debug(f"Redis lock released for port {port}")


def get_available_port(redis_client):
    logger.debug("Searching for available port")
    port = 50000
    maxport = 65535
    while port <= maxport:
        if _acquire_redis_lock(port, redis_client):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(("", port))
                    s.close()  # 释放端口
                    allocated_ports.add(port)
                    logger.info(f"Found and allocated port {port}")
                    return port
                except OSError:
                    logger.debug(f"Port {port} is in use, trying next port")
                    _release_redis_lock(port, redis_client)
                    port += 1
        else:
            port += 1
    logger.error("No available ports found in range 50000-65535")
    raise Exception("No available port")


def release_port(port, redis_client):
    logger.error(f"Attempting to release port {port}")
    with threading.Lock():
        if port in allocated_ports:
            allocated_ports.remove(port)
            _release_redis_lock(port, redis_client)
            logger.info(f"Successfully released port {port}")
        else:
            logger.warning(f"Port {port} was not in allocated_ports set")


def setup_logger():
    """
    设置日志记录器

    Args:

    Returns:
        logging.Logger: 配置好的日志记录器
    """
    config = get_default_config()
    logger.info("Setting up logging configuration")
    # 创建日志目录
    if not os.path.exists(config.Logging.LOG_DIR):
        logger.info(f"Creating log directory: {config.Logging.LOG_DIR}")
        os.makedirs(config.Logging.LOG_DIR)

    config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'format': "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
            },
            'detailed': {
                'format': '[%(asctime)s.%(msecs)03d] [PID %(process)d] [%(threadName)s] [%(name)s] [%(filename)s:%(lineno)d] [%(levelname)s] %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'  # 保留毫秒的3位数字
            }
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': 'detailed',
                'level': config.Logging.LOG_LEVEL,
            },
            'file': {
                'class': 'concurrent_log_handler.ConcurrentRotatingFileHandler',
                'filename': os.path.join(config.Logging.LOG_DIR, config.Logging.LOG_FILENAME),
                'maxBytes': config.Logging.LOG_MAX_BYTES,
                'backupCount': config.Logging.LOG_BACKUP_COUNT,
                'formatter': 'detailed',
                'level': config.Logging.LOG_LEVEL,
                'encoding': 'utf-8'
            }
        },
        'loggers': {
            # 各模块logger，当前未配置，使用root配置
        },
        'root': {
            'level': config.Logging.LOG_LEVEL,
            'handlers': ['file']
        }
    }
    dictConfig(config)
    logger.info("Logging configuration completed")


def generate_random_string(length: int, include_digits: bool = True, include_special_chars: bool = False) -> str:
    """
    生成指定长度的随机字符串

    Args:
        length (int): 需要生成的字符串长度
        include_digits (bool): 是否包含数字，默认为True
        include_special_chars (bool): 是否包含特殊字符，默认为False

    Returns:
        str: 生成的随机字符串

    Examples:
        >>> generate_random_string(8)
        'aB3cD4eF'
        >>> generate_random_string(12, include_special_chars=True)
        'aB3cD4eF@#$%'
    """
    # 定义字符集
    chars = string.ascii_letters
    if include_digits:
        chars += string.digits
    if include_special_chars:
        chars += string.punctuation

    # 生成随机字符串
    return ''.join(random.choice(chars) for _ in range(length))
