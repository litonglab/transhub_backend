import logging
from functools import wraps

from flask_jwt_extended import current_user

logger = logging.getLogger(__name__)


def admin_bypass(f):
    """
    如果当前用户是管理员，直接返回True，否则执行原函数。
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user and current_user.is_admin():
            logger.debug(f"Admin bypass for user {current_user.username}, function {f.__name__}")
            return True
        return f(*args, **kwargs)

    return decorated_function
