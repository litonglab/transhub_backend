import secrets

from flask_jwt_extended import JWTManager
from flask_jwt_extended.exceptions import NoAuthorizationError, InvalidHeaderError

from app_backend.config import JWT_CONFIG
from app_backend.vo import HttpResponse


def init_auth(app):
    # 配置JWT
    app.config['JWT_SECRET_KEY'] = JWT_CONFIG['JWT_SECRET_KEY'] or secrets.token_hex(32)  # 在生产环境中应该使用环境变量
    if not JWT_CONFIG['JWT_SECRET_KEY']:
        app.logger.warning("JWT_SECRET_KEY not set in configuration. Using generated key.")

    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = JWT_CONFIG['JWT_ACCESS_TOKEN_EXPIRES']  # token过期时间，单位秒
    # JWT存储在cookie
    app.config['JWT_TOKEN_LOCATION'] = ['cookies']
    app.config['JWT_COOKIE_SECURE'] = False  # 本地开发用False，生产建议True
    app.config['JWT_ACCESS_COOKIE_PATH'] = '/'
    app.config['JWT_REFRESH_COOKIE_PATH'] = '/'
    app.config['JWT_COOKIE_CSRF_PROTECT'] = False

    jwt = JWTManager(app)

    # 自定义未登录（无token）时的响应
    @app.errorhandler(NoAuthorizationError)
    def handle_no_auth_error(e):
        app.logger.warning(f"Unauthorized access: {e}")
        return HttpResponse.not_authorized('未登录或登录已过期')

    # 自定义token无效时的响应
    @app.errorhandler(InvalidHeaderError)
    def handle_invalid_header_error(e):
        app.logger.warning(f"Invalid token header: {e}")
        return HttpResponse.not_authorized('Token无效')

    # 自定义token过期时的响应（官方推荐写法）
    @jwt.expired_token_loader
    def my_expired_token_callback(jwt_header, jwt_payload):
        app.logger.warning(f"Expired token: {jwt_payload}")
        return HttpResponse.not_authorized('Token已过期，请重新登录')

    @jwt.invalid_token_loader
    def invalid_token_callback(error_string):
        """处理所有无效令牌错误（包括签名验证失败）"""
        app.logger.warning(f"Invalid token: {error_string}")
        return HttpResponse.not_authorized('无效的Token')
