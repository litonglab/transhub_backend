import base64
import logging

from werkzeug.wrappers import Response

from app_backend import get_default_config

config = get_default_config()
logger = logging.getLogger(__name__)


def check_auth(username, password):
    """验证用户名和密码"""
    valid_username = config.DramatiqDashboard.DRAMATIQ_DASHBOARD_USERNAME
    valid_password = config.DramatiqDashboard.DRAMATIQ_DASHBOARD_PASSWORD
    logger.debug(f"dramatiq check auth: username: {username}, password: {password}")
    return username == valid_username and password == valid_password


def authenticate():
    """发送401响应，要求基本认证"""
    return Response(
        'Could not verify your access level for that URL.\n'
        'You have to login with proper credentials', 401,
        {'WWW-Authenticate': 'Basic realm="Dramatiq Dashboard"'}
    )


def create_auth_middleware(dashboard_middleware):
    """创建带有认证的中间件"""

    def auth_middleware(app):
        def wrapped_app(environ, start_response):
            # 获取请求路径
            path = environ.get('PATH_INFO', '')
            dashboard_url = config.DramatiqDashboard.DRAMATIQ_DASHBOARD_URL

            # 如果不是访问 dashboard 路径，直接继续处理请求
            if not path.startswith(dashboard_url):
                return app(environ, start_response)

            # 从 WSGI 环境变量中获取认证信息
            auth_header = environ.get('HTTP_AUTHORIZATION', '')
            if not auth_header.startswith('Basic '):
                return authenticate()(environ, start_response)

            try:
                # 解码认证信息
                auth_decoded = base64.b64decode(auth_header[6:]).decode('utf-8')
                username, password = auth_decoded.split(':', 1)

                if not check_auth(username, password):
                    logger.warning(f"Authentication failed for user: {username}, password: {password}")
                    return authenticate()(environ, start_response)
            except Exception:
                logger.error("Error decoding authentication header", exc_info=True)
                return authenticate()(environ, start_response)

            # 认证通过，继续处理请求
            return dashboard_middleware(app)(environ, start_response)

        return wrapped_app

    return auth_middleware
