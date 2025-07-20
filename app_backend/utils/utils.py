import logging
import os
import random
import socket
import string
from logging.config import dictConfig

# noinspection PyUnresolvedReferences
import concurrent_log_handler
from flask_jwt_extended import current_user

from app_backend import get_default_config

logger = logging.getLogger(__name__)


def get_available_port(redis_client):
    logger.debug("Searching for available port")
    port = 50000
    max_port = 65535
    while port <= max_port:
        lock_name = f"port_lock_{port}"
        logger.info(f"Attempting to acquire Redis lock for port {port}")
        # 设置过期时间为600秒，单个task的运行时间一般不会超过600秒，如果超过，则应调大此值
        result = redis_client.set(lock_name, "locked", nx=True, ex=600)

        if result:
            logger.debug(f"Successfully acquired Redis lock for port {port}")
            # 注：receiver绑定的是ipv6地址
            with socket.socket(socket.AF_INET6, socket.SOCK_DGRAM) as s:
                try:
                    s.bind(("", port))
                    s.close()  # 释放端口
                    logger.info(f"Found and allocated port {port}")
                    return port
                except OSError as e:
                    logger.warning(f"Port {port} maybe in use, trying next port, error msg: {str(e)}")
                    port += 1
        else:
            logger.debug(f"Failed to acquire Redis lock for port {port}, trying next port")
            port += 1
    logger.error("No available ports found in range 50000-65535")
    raise Exception("No available port")


def release_port(port, redis_client):
    lock_name = f"port_lock_{port}"
    logger.debug(f"Releasing Redis lock for port {port}")
    redis_client.delete(lock_name)
    logger.info(f"Successfully released port {port}")


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


def get_record_by_permission(model_cls, admin_filter_dict: dict, user_filter_dict: dict = None):
    """
    通用权限查询函数。管理员可查所有，普通用户只能查自己的。需保证model_cls有user_id字段。
    model_cls: SQLAlchemy模型类
    admin_filter_dict: 管理员查询条件字典
    user_filter_dict: 普通用户查询条件字典（可选，默认为None时使用admin_filter_dict）
    """
    assert current_user is not None, "当前用户未登录，无法进行权限查询"
    if current_user.is_admin():
        logger.debug(f"Admin {current_user.username} querying {model_cls.__name__} with filter {admin_filter_dict}")
        return model_cls.query.filter_by(**admin_filter_dict).first()
    else:
        # 普通用户只能查询自己的记录，传入用户的user_id
        if user_filter_dict is None:
            user_filter_dict = admin_filter_dict
        logger.debug(f"User {current_user.username} querying {model_cls.__name__} with filter {user_filter_dict}")
        return model_cls.query.filter_by(**user_filter_dict, user_id=current_user.user_id).first()
