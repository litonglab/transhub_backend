import logging
import secrets

from flask_jwt_extended import JWTManager
from flask_jwt_extended.exceptions import NoAuthorizationError, InvalidHeaderError

from app_backend.vo.http_response import HttpResponse

logger = logging.getLogger(__name__)


def init_auth(app):
    logger.info("Initializing JWT authentication")
    # 配置JWT
    if not app.config['JWT_SECRET_KEY']:
        logger.warning("JWT_SECRET_KEY not set in configuration. Using generated key.")
        app.config['JWT_SECRET_KEY'] = secrets.token_hex(32)  # 在生产环境中应该使用环境变量

    logger.info(f"JWT access token expiration set to {app.config['JWT_ACCESS_TOKEN_EXPIRES']} seconds")

    # JWT存储在cookie
    app.config['JWT_TOKEN_LOCATION'] = ['cookies']
    app.config['JWT_COOKIE_SECURE'] = False  # 本地开发用False，生产建议True
    app.config['JWT_ACCESS_COOKIE_PATH'] = '/'
    app.config['JWT_REFRESH_COOKIE_PATH'] = '/'
    app.config['JWT_COOKIE_CSRF_PROTECT'] = False

    jwt = JWTManager(app)
    logger.info("JWT manager initialized")

    # 自定义未登录（无token）时的响应
    @app.errorhandler(NoAuthorizationError)
    def handle_no_auth_error(e):
        logger.warning(f"Unauthorized access attempt: {str(e)}")
        logger.debug(f"Request details: {e}")
        return HttpResponse.not_authorized('未登录或登录已过期')

    # 自定义token无效时的响应
    @app.errorhandler(InvalidHeaderError)
    def handle_invalid_header_error(e):
        logger.warning(f"Invalid token header detected: {str(e)}")
        logger.debug(f"Invalid header details: {e}")
        return HttpResponse.not_authorized('Token无效')

    # 自定义token过期时的响应（官方推荐写法）
    @jwt.expired_token_loader
    def my_expired_token_callback(jwt_header, jwt_payload):
        logger.warning(f"Expired token detected: {jwt_payload}")
        logger.debug(f"Token expiration details - Header: {jwt_header}, Payload: {jwt_payload}")
        return HttpResponse.not_authorized('Token已过期，请重新登录')

    @jwt.invalid_token_loader
    def invalid_token_callback(error_string):
        """处理所有无效令牌错误（包括签名验证失败）"""
        logger.warning(f"Invalid token detected: {error_string}")
        logger.debug(f"Invalid token details: {error_string}")
        return HttpResponse.not_authorized('无效的Token')

    @jwt.user_lookup_loader
    def user_lookup_callback(_jwt_header, jwt_data):
        """
        注册一个回调函数，在访问受保护的路由时从数据库自动加载用户（current_user）。
        这应该在成功查找时返回任何 python 对象，或者如果查找因任何原因失败
        （例如，如果用户已从数据库中删除）则返回 None。
        """
        from app_backend.model.user_model import UserModel
        
        try:
            # 从JWT payload中获取用户ID
            user_id = jwt_data.get('sub')
            if not user_id:
                logger.warning("JWT payload missing user ID (sub claim)")
                return None
            
            # 从数据库查询用户
            user = UserModel.query.get(user_id)
            if not user:
                logger.warning(f"User not found in database for ID: {user_id}")
                return None
            
            # 检查用户是否被软删除
            if user.is_deleted:
                logger.warning(f"User {user.username} (ID: {user_id}) has been deleted")
                return None
            
            # 检查用户是否被锁定
            if user.is_locked:
                logger.warning(f"User {user.username} (ID: {user_id}) is locked")
                return None
            
            logger.debug(f"Successfully loaded user: {user.username} (ID: {user_id})")
            return user
            
        except Exception as e:
            logger.error(f"Error loading user from JWT: {e}")
            return None

    logger.info("JWT authentication initialization completed")
