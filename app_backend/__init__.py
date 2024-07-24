from datetime import datetime
from flask import Flask
from flask_cors import CORS
from flask_redis import FlaskRedis
from flask_rq2 import RQ
from flask_sqlalchemy import SQLAlchemy

redis_client = FlaskRedis()
rq = RQ()
db = SQLAlchemy()


def make_dir():
    import os
    from app_backend.config import USER_DIR_PATH, BASEDIR, ALL_CLASS_PATH
    if not os.path.exists(BASEDIR):
        os.makedirs(BASEDIR)
        print('make base dir')
    if not os.path.exists(USER_DIR_PATH):
        os.makedirs(USER_DIR_PATH)
        print('make user dir')
    for name, dir in ALL_CLASS_PATH.items():
        if not os.path.exists(dir):
            os.makedirs(dir)
            print('make summary dir: ', dir)
    return


def create_app():
    app = Flask(__name__)
    CORS(app, supports_credentials=True, origins='*')
    app.config.from_object('app_backend.config')
    redis_client.init_app(app)
    rq.init_app(app)

    # 使用当前时间做hash，作为session的key
    app.secret_key = str(hash(str(datetime.now())))
    # app_backend.config[
    #     'SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:1160234413@172.20.240.1:3306/transhub_base'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://' + app.config['MYSQL_USERNAME'] + ':' + app.config[
        'MYSQL_PASSWORD'] + '@' + app.config['MYSQL_ADDRESS'] + '/' + app.config['MYSQL_DBNAME']
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
    db.init_app(app)
    with app.app_context():
        try:
            from app_backend.model.User_model import User_model
            from app_backend.model.Task_model import Task_model
            from app_backend.model.Rank_model import Rank_model
            from app_backend.model.Competition_model import Competition_model
            db.create_all()
            print('create all tables')
        except Exception as e:
            print(e)
        make_dir()
        # Register blueprints
        from app_backend.views.user import user_bp
        from app_backend.views.task import task_bp
        from app_backend.views.help import help_bp
        # from .views.graph import graph_bp
        from app_backend.views.history import history_bp
        # from .views.config import config_bp
        from .views.summary import summary_bp
        # from .views.log import log_bp
        from .views.source_code import source_code_bp

        app.register_blueprint(user_bp)
        app.register_blueprint(history_bp)
        app.register_blueprint(task_bp)
        app.register_blueprint(help_bp)
        # app_backend.register_blueprint(graph_bp)
        # app_backend.register_blueprint(config_bp)
        app.register_blueprint(summary_bp)
        # app_backend.register_blueprint(log_bp)
        app.register_blueprint(source_code_bp)
        return app
