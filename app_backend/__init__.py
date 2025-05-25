import os
from datetime import datetime
from flask import Flask, render_template
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

    dist_path = 'app_frontend_dist/dist'
    dist_path = os.path.abspath(dist_path)
    print(f"frontend dist path: {dist_path}")
    # 判断dist_path是否存在，用于判断前端是否随后端一起打包
    if not os.path.exists(dist_path):
        print("前端dist文件夹不存在，请单独部署前端")
        app = Flask(__name__)
    else:
        print("前端dist文件夹存在，前端随后端一同部署")
        app = Flask(__name__,
                    static_folder=dist_path + '/assets', template_folder=dist_path)

        # 未定义路由重定向到前端，由前端处理
        @app.errorhandler(404)
        def index(args):
            # logger.info('404 handler, args: ' + str(args))
            return render_template("index.html")
    CORS(app, supports_credentials=True, origins='*')

    app.config.from_object('app_backend.config')
    redis_client.init_app(app)
    # rq.init_app(app)

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
        
        # 初始化认证
        from app_backend.security.auth import init_auth
        init_auth(app)

        # 全局错误处理，统一json返回
        from flask import jsonify
        from werkzeug.exceptions import HTTPException
        
        def handle_http_exception(e):
            response = e.get_response()
            response.data = jsonify({
                "code": e.code,
                "message": e.description
            }).data
            response.content_type = "application/json"
            return response
        
        def handle_exception(e):
            return jsonify({
                "code": 500,
                "message": str(e)
            }), 500
        
        app.register_error_handler(HTTPException, handle_http_exception)
        app.register_error_handler(Exception, handle_exception)
        
        end_time = time.time()
        print(f"App context loaded in {end_time - start_time} seconds")

    return app
