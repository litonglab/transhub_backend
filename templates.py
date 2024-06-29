import pymysql
import MySQLdb

# from DBUtils.PooledDB import PooledDB
from dbutils.pooled_db import PooledDB
pool = PooledDB(MySQLdb, 8, # 最低预启动连接数
                host="localhost",
                port=3306,
                user='root',
                passwd='1160234413',
                db='transhub_base',
                charset="utf8")

conn = pymysql.connect(
        host="localhost",
        port=3306,
        user='root',
        passwd='1160234413',
        db='transhub_base',
        charset="utf8"
        )

def select(sql):
    conn = pool.connection()
    cursor = conn.cursor()
    cursor.execute(sql)
    result = cursor.fetchall()
    cursor.close()
    conn.close()
    return result
 
def insert(sql):
    conn = pool.connection()
    cursor = conn.cursor()
    try:
        cursor.execute(sql)
        conn.commit()
        return {'result':True, 'id':int(cursor.lastrowid)}
    except Exception as err:
        conn.rollback()
        return {'result':False, 'err':err}
    finally:
        cursor.close()
        conn.close()

def update(sql):
    conn = pool.connection()
    cursor = conn.cursor()
    try:
        cursor.execute(sql)
        conn.commit()
        return {'result':True, 'id':int(cursor.lastrowid)}
    except Exception as err:
        conn.rollback()
        return {'result':False, 'err':err}
    finally:
        cursor.close()
        conn.close()
