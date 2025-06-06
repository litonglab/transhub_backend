import logging
import os
import socket
import threading
from logging.config import dictConfig

# noinspection PyUnresolvedReferences
import concurrent_log_handler
import redis

from app_backend.config import LOG_CONFIG, REDIS_CONFIG

# 配置Redis客户端
redis_client = redis.Redis(host=REDIS_CONFIG['REDIS_ADDRESS'], port=REDIS_CONFIG['REDIS_PORT'],
                           db=REDIS_CONFIG['REDIS_DB'])

# 用于管理分配的端口
allocated_ports = set()
logger = logging.getLogger(__name__)


def acquire_redis_lock(port):
    lock_name = f"port_lock_{port}"
    logger.debug(f"Attempting to acquire Redis lock for port {port}")
    result = redis_client.set(lock_name, "locked", nx=True, ex=600)  # 设置过期时间为60秒
    if result:
        logger.debug(f"Successfully acquired Redis lock for port {port}")
    else:
        logger.error(f"Failed to acquire Redis lock for port {port}")
    return result


def release_redis_lock(port):
    lock_name = f"port_lock_{port}"
    logger.debug(f"Releasing Redis lock for port {port}")
    redis_client.delete(lock_name)
    logger.debug(f"Redis lock released for port {port}")


def get_available_port():
    logger.debug("Searching for available port")
    port = 50000
    maxport = 65535
    while port <= maxport:
        if acquire_redis_lock(port):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(("", port))
                    s.close()  # 释放端口
                    allocated_ports.add(port)
                    logger.info(f"Found and allocated port {port}")
                    return port
                except OSError:
                    logger.debug(f"Port {port} is in use, trying next port")
                    release_redis_lock(port)
                    port += 1
        else:
            port += 1
    logger.error("No available ports found in range 50000-65535")
    raise Exception("No available port")


def release_port(port):
    logger.error(f"Attempting to release port {port}")
    with threading.Lock():
        if port in allocated_ports:
            allocated_ports.remove(port)
            release_redis_lock(port)
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
    logger.info("Setting up logging configuration")
    # 创建日志目录
    if not os.path.exists(LOG_CONFIG["LOG_DIR"]):
        logger.info(f"Creating log directory: {LOG_CONFIG['LOG_DIR']}")
        os.makedirs(LOG_CONFIG["LOG_DIR"])

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
                'level': LOG_CONFIG["LOG_LEVEL"]
            },
            'file': {
                'class': 'concurrent_log_handler.ConcurrentRotatingFileHandler',
                'filename': os.path.join(LOG_CONFIG["LOG_DIR"], LOG_CONFIG["LOG_FILENAME"]),
                'maxBytes': LOG_CONFIG["LOG_MAX_BYTES"],
                'backupCount': LOG_CONFIG["LOG_BACKUP_COUNT"],
                'formatter': 'detailed',
                'level': LOG_CONFIG["LOG_LEVEL"],
                'encoding': 'utf-8'
            }
        },
        'loggers': {
            # 各模块logger，当前未配置，使用root配置
        },
        'root': {
            'level': LOG_CONFIG["LOG_LEVEL"],
            'handlers': ['file']
        }
    }
    dictConfig(config)
    logger.info("Logging configuration completed")
