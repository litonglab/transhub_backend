from flask_jwt_extended import JWTManager
from flask_jwt_extended.exceptions import NoAuthorizationError, InvalidHeaderError

from app_backend.vo import HttpResponse


def init_auth(app):
    # 配置JWT
    app.config['JWT_SECRET_KEY'] = 'your-secret-key'  # 在生产环境中应该使用环境变量
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = 3 * 24 * 60 * 60  # token过期时间，单位秒
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
        return HttpResponse.not_authorized('未登录或登录已过期')

    # 自定义token无效时的响应
    @app.errorhandler(InvalidHeaderError)
    def handle_invalid_header_error(e):
        return HttpResponse.not_authorized('Token无效')

    # 自定义token过期时的响应（官方推荐写法）
    @jwt.expired_token_loader
    def my_expired_token_callback(jwt_header, jwt_payload):
        return HttpResponse.not_authorized('Token已过期，请重新登录')
