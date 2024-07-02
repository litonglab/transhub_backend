from flask_redis import FlaskRedis
from flask_rq2 import RQ
from flask_sqlalchemy import SQLAlchemy

# from templates import conn

redis_client = FlaskRedis()
rq = RQ()
# cur = conn.cursor()
db = SQLAlchemy()
