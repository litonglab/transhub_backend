import os
import secrets
import threading
from logging import getLogger

import dramatiq_dashboard
from dramatiq.brokers.redis import RedisBroker
from flask import Flask, render_template
from flask_caching import Cache
from flask_cors import CORS
from flask_redis import FlaskRedis
from flask_sqlalchemy import SQLAlchemy
from werkzeug.exceptions import HTTPException

from app_backend.config import get_config, get_default_config
from app_backend.security.auth import init_auth
from app_backend.security.dramatiq_auth import create_auth_middleware
from app_backend.utils.utils import setup_logger
from app_backend.vo import HttpResponse

config = get_default_config()
# Initialize extensions
# Flask extensions for Redis and SQLAlchemy, init and used in app_context for safety
redis_client = FlaskRedis()
db = SQLAlchemy()
cache = Cache()

# Configure logging
setup_logger()
logger = getLogger(__name__)

# Global app instance and lock for the singleton pattern
_app_instance = None
_app_lock = threading.Lock()


def singleton_app(func):
    """
    Decorator to implement the singleton pattern for Flask app creation.
    Ensures thread-safe singleton behavior with optional force_new parameter.
    """

    def wrapper(force_new=False):
        global _app_instance

        # Check if we already have an instance and don't need to force a new one
        if _app_instance is not None and not force_new:
            logger.debug("Returning existing app instance")
            return _app_instance

        # Use the double-checked locking pattern for thread safety
        with _app_lock:
            # Check again inside the lock in case another thread created the instance
            if _app_instance is not None and not force_new:
                logger.debug("Returning existing app instance (created by another thread)")
                return _app_instance

            # Create new instance
            if force_new and _app_instance is not None:
                logger.info("Creating new app instance (forced)")
            else:
                logger.info("Creating new app instance (first time)")

            _app_instance = func()
            return _app_instance

    return wrapper


def _make_dir():
    """Create the necessary directories for the application."""
    directories = [
        (config.App.BASEDIR, 'base directory'),
        (config.App.USER_DIR_PATH, 'user directory')
    ]

    # Create base directories
    for dir_path, dir_name in directories:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
            logger.info(f'Created {dir_name}: {dir_path}')

    # Create class-specific directories
    for name, _config in config.Course.ALL_CLASS.items():
        dir_path = _config['path']
        if not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
            logger.info(f'Created class directory for {name}: {dir_path}')


def _configure_cors(app):
    """Configure CORS settings based on environment."""

    allowed_origins = config.Security.CORS_ORIGINS

    # 处理逗号分隔的多个域名
    if isinstance(allowed_origins, str) and ',' in allowed_origins:
        allowed_origins = [origin.strip() for origin in allowed_origins.split(',')]

    if allowed_origins == '*' or (isinstance(allowed_origins, list) and '*' in allowed_origins):
        logger.warning("CORS is configured to allow all origins. Consider restricting in production.")

    CORS(app, supports_credentials=True, origins=allowed_origins)


def _configure_database(app):
    """Configure database connection."""
    db.init_app(app)


def _configure_redis(app):
    """Configure redis."""
    # Initialize Redis
    redis_client.init_app(app)
    # 判断redis是否连接成功
    redis_client.ping()


def _configure_cache(app):
    """Configure Flask-Caching."""
    cache.init_app(app, config={
        'CACHE_TYPE': 'redis',
        'CACHE_REDIS_URL': config.Cache.FLASK_REDIS_URL,
        'CACHE_DEFAULT_TIMEOUT': 10,  # 默认缓存时间为10秒
        'CACHE_OPTIONS': {
            'socket_timeout': 5,  # Redis连接超时时间
            'socket_connect_timeout': 5,  # Redis连接建立超时时间
            'retry_on_timeout': True  # 超时时重试
        }
    })
    logger.info("Cache configured with Redis backend")


def _configure_secret_key(app):
    """Configure secret key for Flask app."""
    if not app.config['SECRET_KEY']:
        logger.warning("⚠️ SECRET_KEY 未设置，使用自动生成的密钥。请在生产环境中设置此变量以增强安全性。")
        app.config['SECRET_KEY'] = secrets.token_hex(32)


# get_app() used in dramatiq worker.
@singleton_app
def get_app():
    """
    Get Flask application instance using the singleton pattern.

    This function is decorated with @singleton_app to ensure only one
    instance of the Flask application exists throughout the application lifecycle.

    The singleton decorator supports a force_new parameter:
    - get_app() - Returns existing instance or creates new one
    - get_app(force_new=True) - Forces creation of new instance

    Returns:
        Flask: The Flask application instance.
    """
    import time
    start_time = time.time()

    # app = Flask(__name__)

    dist_path = os.path.abspath('app_frontend_dist/dist')
    logger.info(f"Frontend dist path: {dist_path}")

    if os.path.exists(dist_path):
        logger.info("Frontend dist folder exists, deploying frontend with backend")
        app = Flask(__name__,
                    static_folder=dist_path + '/assets', template_folder=dist_path)

        # Handle 404 errors by serving frontend
        @app.errorhandler(404)
        def handle_404(error):
            return render_template("index.html")
    else:
        app = Flask(__name__)
        logger.warning("Frontend dist folder not found, please deploy frontend separately")

    # Load configuration
    app.config.from_prefixed_env()

    # Configure components
    _configure_database(app)
    _configure_redis(app)
    _configure_cache(app)

    end_time = time.time()

    logger.info(f"App initialized in {end_time - start_time:.3f} seconds")
    return app


def reset_app():
    """
    Reset the singleton app instance.
    Useful for testing or when you need to completely reinitialize the app.
    """
    global _app_instance
    with _app_lock:
        if _app_instance is not None:
            logger.info("Resetting app instance")
            _app_instance = None
        else:
            logger.debug("No app instance to reset")


def get_app_instance():
    """
    Get the current app instance without creating a new one.

    Returns:
        Flask or None: The current Flask app instance, or None if not created yet.
    """
    return _app_instance


def is_app_initialized():
    """
    Check if the Flask app has been initialized.

    Returns:
        bool: True if app instance exists, False otherwise.
    """
    return _app_instance is not None


def get_app_info():
    """
    Get information about the current app instance.

    Returns:
        dict: Information about the app instance including status and config.
    """
    if _app_instance is None:
        return {
            "initialized": False,
            "instance_id": None,
            "config_loaded": False
        }

    return {
        "initialized": True,
        "instance_id": id(_app_instance),
        "config_loaded": bool(_app_instance.config),
        "debug_mode": _app_instance.debug,
        "testing": _app_instance.testing,
        "secret_key_set": bool(_app_instance.secret_key)
    }


def _create_tables(app):
    """Create database tables."""
    try:
        # Import models to register them with SQLAlchemy
        from app_backend.model.User_model import User_model
        from app_backend.model.Task_model import Task_model
        from app_backend.model.Rank_model import Rank_model
        from app_backend.model.graph_model import graph_model
        from app_backend.model.Competition_model import Competition_model

        db.create_all()
        logger.info('Database tables created successfully')
    except Exception as e:
        logger.error(f'Failed to create database tables: {e}')
        raise


def _register_blueprints(app):
    """Register all application blueprints."""
    from app_backend.views.user import user_bp
    from app_backend.views.task import task_bp
    from app_backend.views.help import help_bp
    from app_backend.views.history import history_bp
    from app_backend.views.summary import summary_bp
    from app_backend.views.source_code import source_code_bp
    from app_backend.views.graph import graph_bp

    blueprints = [
        (user_bp, 'user'),
        (history_bp, 'history'),
        (task_bp, 'task'),
        (help_bp, 'help'),
        (summary_bp, 'summary'),
        (source_code_bp, 'source_code'),
        (graph_bp, 'graph'),
    ]

    for blueprint, name in blueprints:
        app.register_blueprint(blueprint)
        logger.info(f'Registered blueprint: {name}')


def _configure_error_handlers(app):
    """Configure global error handlers."""

    def handle_http_exception(e):
        """Handle HTTP exceptions with JSON response."""
        return HttpResponse.error(e.code, e.description)

    def handle_exception(e):
        """Handle general exceptions with JSON response."""
        logger.error(f'The Unhandled exception details: {e}', exc_info=True)
        return HttpResponse.error(500, "Internal Server Error")

    app.register_error_handler(HTTPException, handle_http_exception)
    app.register_error_handler(Exception, handle_exception)


def _initialize_auth(app):
    """Initialize the authentication system."""
    try:
        init_auth(app)
        logger.info('Authentication system initialized')
    except Exception as e:
        logger.error(f'Failed to initialize authentication: {e}')
        raise


def _configure_dramatiq_dashboard(app):
    """配置 dramatiq dashboard 中间件"""
    if not config.DramatiqDashboard.DRAMATIQ_DASHBOARD_ENABLED:
        logger.warning("Dramatiq dashboard is disabled in the configuration.")
        return
    try:
        # 创建 dramatiq dashboard 中间件
        redis_broker = RedisBroker(url=config.Cache.FLASK_REDIS_URL)
        redis_broker.declare_queue("default")
        dashboard_middleware = dramatiq_dashboard.make_wsgi_middleware(
            config.DramatiqDashboard.DRAMATIQ_DASHBOARD_URL, redis_broker)

        # 创建并应用带有认证的中间件
        auth_middleware = create_auth_middleware(dashboard_middleware)
        app.wsgi_app = auth_middleware(app.wsgi_app)

        logger.info('Dramatiq dashboard middleware configured successfully')
    except Exception as e:
        logger.error(f'Failed to configure dramatiq dashboard middleware: {e}')


def create_app():
    """Create and fully configure Flask application."""
    import time
    start_time = time.time()

    # Get basic app instance
    app = get_app()

    with app.app_context():
        # Create database tables
        _create_tables(app)
        # Create the necessary directories
        _make_dir()
        # Register blueprints
        _register_blueprints(app)
        # Initialize authentication
        _initialize_auth(app)
        # Configure error handlers
        _configure_error_handlers(app)
        # Configure dramatiq dashboard middleware
        _configure_dramatiq_dashboard(app)
        # Configure secret key
        _configure_secret_key(app)
        # Configure cors
        _configure_cors(app)

        end_time = time.time()
        logger.info(f"App fully configured in {end_time - start_time:.3f} seconds")
        # print(app.config)

    return app
