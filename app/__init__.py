from datetime import datetime

from flask import Flask
from flask_cors import CORS

from app.extensions import redis_client, rq, db

from app.model import User_model, Task_model
from flask_sqlalchemy import SQLAlchemy


def create_app():
    app = Flask(__name__)
    CORS(app, supports_credentials=True, origins='*')
    app.config.from_object('app.config')
    redis_client.init_app(app)
    rq.init_app(app)

    # 使用当前时间做hash，作为session的key
    app.secret_key = str(hash(str(datetime.now())))
    app.config[
        'SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:1160234413@172.20.240.1:3306/transhub_base?charset=utf8'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
    db.init_app(app)
    with app.app_context():
        try:
            db.create_all()
            print('create all tables')
        except Exception as e:
            print(e)

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
