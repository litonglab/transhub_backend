from flask import Flask
from flask_cors import CORS

from app.extensions import redis_client, rq

from app.models import create_task_table
from app.model.User_model import create_user_table


def create_app():
    app = Flask(__name__)
    CORS(app, supports_credentials=True, origins='*')
    app.config.from_object('app.config')
    redis_client.init_app(app)
    rq.init_app(app)
    create_task_table()
    create_user_table()
    with app.app_context():
        # Register blueprints
        from .views.user import user_bp
        from .views.task import task_bp
        from .views.help import help_bp
        from .views.graph import graph_bp
        from .views.history import history_bp
        # from .views.config import config_bp
        from .views.summary import summary_bp
        from .views.log import log_bp
        from .views.source_code import source_code_bp

        app.register_blueprint(user_bp)
        app.register_blueprint(history_bp)
        app.register_blueprint(task_bp)
        app.register_blueprint(help_bp)
        app.register_blueprint(graph_bp)
        # app.register_blueprint(config_bp)
        app.register_blueprint(summary_bp)
        app.register_blueprint(log_bp)
        app.register_blueprint(source_code_bp)

    return app
