from datetime import datetime
from flask import Flask
from flask_cors import CORS
from flask_redis import FlaskRedis
# from flask_rq2 import RQ
from flask_sqlalchemy import SQLAlchemy
# import dramatiq
# from dramatiq.brokers.redis import RedisBroker
# from dramatiq.middleware import TimeLimit
import time
redis_client = FlaskRedis()
# rq = RQ()

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


def get_app():
    st = time.time()
    app = Flask(__name__)
    CORS(app, supports_credentials=True, origins='*')
    app.config.from_object('app_backend.config')
    redis_client.init_app(app)
    #rq.init_app(app)

    app.secret_key = str(hash(str(datetime.now())))
    app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://' + app.config['MYSQL_USERNAME'] + ':' + app.config[
            'MYSQL_PASSWORD'] + '@' + app.config['MYSQL_ADDRESS'] + '/' + app.config['MYSQL_DBNAME']
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
    db.init_app(app)
    et = time.time()
    print(f"App initialized in {et - st} seconds")
    return app


def create_app():
    start_time = time.time()
    app = get_app()
    with app.app_context():
        try:
            from app_backend.model.User_model import User_model
            from app_backend.model.Task_model import Task_model
            from app_backend.model.Rank_model import Rank_model
            from app_backend.model.graph_model import graph_model
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
        from app_backend.views.history import history_bp
        from app_backend.views.summary import summary_bp
        from app_backend.views.source_code import source_code_bp
        from app_backend.views.graph import graph_bp

        app.register_blueprint(user_bp)
        app.register_blueprint(history_bp)
        app.register_blueprint(task_bp)
        app.register_blueprint(help_bp)
        app.register_blueprint(summary_bp)
        app.register_blueprint(source_code_bp)
        app.register_blueprint(graph_bp)
        end_time = time.time()
        print(f"App context loaded in {end_time- start_time} seconds")

    return app
