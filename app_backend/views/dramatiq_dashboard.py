import logging

import dramatiq_dashboard
from dramatiq.brokers.redis import RedisBroker
from flask import Blueprint, request, Response
from flask_jwt_extended import jwt_required, current_user

from app_backend import get_default_config
from app_backend.security.admin_decorators import admin_required
from app_backend.vo.http_response import HttpResponse

logger = logging.getLogger(__name__)
config = get_default_config()

dramatiq_dashboard_bp = Blueprint('dramatiq_dashboard', __name__)

# 在模块级别创建 Redis broker 和 dashboard 中间件，避免每次请求都创建
_redis_broker = None
_dashboard_middleware = None


def _get_dashboard_middleware():
    """获取 dashboard 中间件，懒加载单例模式"""
    global _redis_broker, _dashboard_middleware

    if _dashboard_middleware is None:
        try:
            # 创建 redis broker
            _redis_broker = RedisBroker(url=config.Cache.FLASK_REDIS_URL)
            _redis_broker.declare_queue("default")

            # 创建 dramatiq dashboard 中间件
            _dashboard_middleware = dramatiq_dashboard.make_wsgi_middleware(
                '/dramatiq', _redis_broker)

            logger.info("Dramatiq dashboard middleware initialized")
        except Exception as e:
            logger.error(f"Failed to initialize dramatiq dashboard middleware: {e}")
            raise

    return _dashboard_middleware


@dramatiq_dashboard_bp.route('/dramatiq/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
@dramatiq_dashboard_bp.route('/dramatiq/', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
@dramatiq_dashboard_bp.route('/dramatiq', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
@jwt_required()
@admin_required()
def dramatiq_dashboard_proxy(path=''):
    """
    代理到 dramatiq dashboard 的请求
    仅admin认证用户可访问
    """
    try:
        logger.info(f"User {current_user.username} accessing dramatiq dashboard at path: {path}")
        # 获取预初始化的 dashboard 中间件
        dashboard_middleware = _get_dashboard_middleware()
        # 准备 WSGI 环境
        environ = request.environ.copy()

        # 重写环境变量，修正路径以匹配 dashboard URL
        environ['PATH_INFO'] = '/dramatiq/' + path
        environ['SCRIPT_NAME'] = ''

        # 收集响应数据
        response_data = []
        response_status = None
        response_headers = None

        def capture_start_response(status, _headers):
            nonlocal response_status, response_headers
            response_status = status
            response_headers = _headers
            return response_data.append

        # 创建一个虚拟的 WSGI 应用来调用中间件
        def dummy_app(env, start_resp):
            start_resp('404 Not Found', [('Content-Type', 'text/plain')])
            return [b'Not Found']

        # 调用中间件
        app_iter = dashboard_middleware(dummy_app)(environ, capture_start_response)

        # 收集响应体
        try:
            for data in app_iter:
                if data:
                    response_data.append(data)
        finally:
            if hasattr(app_iter, 'close'):
                app_iter.close()

        # 构建响应
        if response_status:
            status_code = int(response_status.split(' ', 1)[0])
            body = b''.join(response_data)
            headers = dict(response_headers) if response_headers else {}
            # 移除可能冲突的头部
            headers.pop('content-length', None)

            # 对于成功响应，直接返回原始响应
            if 200 <= status_code < 400:
                return Response(body, status=status_code, headers=headers)
            elif 400 <= status_code < 500:
                return HttpResponse.error(status_code, f'Dashboard client error: {status_code}')
            else:
                return HttpResponse.error(status_code, f'Dashboard server error: {status_code}')
        else:
            return HttpResponse.error(503, 'Dashboard not available')

    except Exception as e:
        logger.error(f'Error accessing dramatiq dashboard: {e}', exc_info=True)
        return HttpResponse.internal_error(f'Internal server error: {str(e)}')


def cleanup_dashboard_middleware():
    """清理 dashboard 中间件资源"""
    global _redis_broker, _dashboard_middleware

    try:
        if _redis_broker:
            _redis_broker.close()
            _redis_broker = None

        _dashboard_middleware = None
        logger.info("Dramatiq dashboard middleware cleaned up")
    except Exception as e:
        logger.error(f"Error cleaning up dramatiq dashboard middleware: {e}")


# 在 Flask 应用关闭时注册清理函数
def register_cleanup_handler(app):
    """注册清理处理器"""

    @app.teardown_appcontext
    def cleanup_handler(error):
        if error:
            logger.error(f"App context teardown with error: {error}")

    # 当进程退出时清理资源
    import atexit
    atexit.register(cleanup_dashboard_middleware)
    logger.info("Dramatiq dashboard middleware registered")
