import os
import secrets
import threading
from logging import getLogger

from flask import Flask, render_template
from flask_cors import CORS
from flask_redis import FlaskRedis
from flask_sqlalchemy import SQLAlchemy
from werkzeug.exceptions import HTTPException

from app_backend.config import USER_DIR_PATH, BASEDIR, ALL_CLASS
from app_backend.utils.utils import setup_logger
from app_backend.vo import HttpResponse

# Initialize extensions
redis_client = FlaskRedis()
db = SQLAlchemy()

# Configure logging
setup_logger()
logger = getLogger(__name__)

# Global app instance and lock for singleton pattern
_app_instance = None
_app_lock = threading.Lock()


def singleton_app(func):
    """
    Decorator to implement singleton pattern for Flask app creation.
    Ensures thread-safe singleton behavior with optional force_new parameter.
    """

    def wrapper(force_new=False):
        global _app_instance

        # Check if we already have an instance and don't need to force a new one
        if _app_instance is not None and not force_new:
            logger.debug("Returning existing app instance")
            return _app_instance

        # Use double-checked locking pattern for thread safety
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


def make_dir():
    """Create necessary directories for the application."""

    directories = [
        (BASEDIR, 'base directory'),
        (USER_DIR_PATH, 'user directory')
    ]

    # Create base directories
    for dir_path, dir_name in directories:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
            logger.info(f'Created {dir_name}: {dir_path}')

    # Create class-specific directories
    for name, _config in ALL_CLASS.items():
        dir_path = _config['path']
        if not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
            logger.info(f'Created class directory for {name}: {dir_path}')


def _configure_cors(app):
    """Configure CORS settings based on environment."""
    # Get allowed origins from config
    allowed_origins = app.config.get('CORS_ORIGINS', '*')
    if allowed_origins == '*':
        logger.warning("CORS is configured to allow all origins. Consider restricting in production.")

    CORS(app, supports_credentials=True, origins=allowed_origins)


def _configure_database(app):
    """Configure database connection."""
    # Build database URI
    db_uri = (
        f"mysql+pymysql://{app.config['MYSQL_CONFIG']['MYSQL_USERNAME']}:"
        f"{app.config['MYSQL_CONFIG']['MYSQL_PASSWORD']}@{app.config['MYSQL_CONFIG']['MYSQL_ADDRESS']}/"
        f"{app.config['MYSQL_CONFIG']['MYSQL_DBNAME']}"
    )
    app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Disable to save resources

    db.init_app(app)


@singleton_app
def get_app():
    """
    Get Flask application instance using singleton pattern.

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
    app.config.from_object('app_backend.config')

    # Generate secure secret key
    app.secret_key = os.getenv('SECRET_KEY') or secrets.token_hex(32)
    if not os.getenv('SECRET_KEY'):
        logger.warning("SECRET_KEY not set in environment. Using generated key.")

    # Configure components
    _configure_cors(app)
    _configure_database(app)

    # Initialize Redis
    redis_client.init_app(app)

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


def _initialize_database(app):
    """Initialize database tables."""
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
        (graph_bp, 'graph')
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
    """Initialize authentication system."""
    try:
        from app_backend.security.auth import init_auth
        init_auth(app)
        logger.info('Authentication system initialized')
    except Exception as e:
        logger.error(f'Failed to initialize authentication: {e}')
        raise


def create_app():
    """Create and fully configure Flask application."""
    import time
    start_time = time.time()

    # Get basic app instance
    app = get_app()

    with app.app_context():
        # Initialize database
        _initialize_database(app)

        # Create necessary directories
        make_dir()

        # Register blueprints
        _register_blueprints(app)

        # Initialize authentication
        _initialize_auth(app)

        # Configure error handlers
        _configure_error_handlers(app)

        end_time = time.time()
        logger.info(f"App fully configured in {end_time - start_time:.3f} seconds")

    return app
