import logging
from flask_jwt_extended import current_user
from functools import wraps

from app_backend.vo.http_response import HttpResponse

logger = logging.getLogger(__name__)


def admin_required(allow_super_admin_only=False):
    """
    管理员权限验证装饰器
    
    Args:
        allow_super_admin_only: 是否只允许超级管理员访问
        
    注意：使用了@jwt.user_lookup_loader，current_user会自动从数据库加载，
    并且已经过滤了被删除和锁定的用户
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 使用current_user，它会通过user_lookup_loader自动加载并验证用户
            user = current_user

            if not user:
                # user_lookup_loader返回None意味着用户不存在、被删除或被锁定
                logger.warning(f"Admin access denied: User not found, deleted, or locked")
                return HttpResponse.not_authorized('用户不存在或账户已被禁用')

            if allow_super_admin_only:
                if not user.is_super_admin():
                    logger.warning(f"Super admin access denied for user {user.username}")
                    return HttpResponse.forbidden('需要超级管理员权限')
            else:
                if not user.is_admin():
                    logger.warning(f"Admin access denied for user {user.username}")
                    return HttpResponse.forbidden('需要管理员权限')

            return f(*args, **kwargs)

        return decorated_function

    return decorator


def _check_role(roles, exclude=False):
    """
    角色校验公共逻辑

    Args:
        roles: 角色列表
        exclude: False 表示白名单（角色必须在列表中），True 表示黑名单（角色不能在列表中）

    Returns:
        校验通过返回 None，否则返回 HttpResponse 错误响应
    """
    user = current_user

    if not user:
        logger.warning(f"Role check: User not found, deleted, or locked")
        return HttpResponse.not_authorized('用户不存在或账户已被禁用')

    role_matched = user.role in roles
    if (exclude and role_matched) or (not exclude and not role_matched):
        logger.warning(
            f"Role check failed: user {user.username} has role {user.role}, "
            f"{'excluded' if exclude else 'required'}: {roles}")
        return HttpResponse.forbidden('权限不足')

    return None


def role_excluded(*excluded_roles):
    """
    角色排除装饰器，拒绝指定角色的用户访问

    Args:
        excluded_roles: 被排除的角色列表

    注意：使用了@jwt.user_lookup_loader，current_user会自动从数据库加载，
    并且已经过滤了被删除和锁定的用户
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            error = _check_role(excluded_roles, exclude=True)
            if error:
                return error
            return f(*args, **kwargs)

        return decorated_function

    return decorator


def role_required(*allowed_roles):
    """
    角色权限验证装饰器

    Args:
        allowed_roles: 允许的角色列表

    注意：使用了@jwt.user_lookup_loader，current_user会自动从数据库加载，
    并且已经过滤了被删除和锁定的用户
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            error = _check_role(allowed_roles, exclude=False)
            if error:
                return error
            return f(*args, **kwargs)

        return decorated_function

    return decorator
