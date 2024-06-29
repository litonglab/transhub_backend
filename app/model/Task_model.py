from app.extensions import cur
from templates import conn, pool, select, insert, update

class Task_model:
    def __init__(self):
        self.id = None
        self.task_id = None
        self.user_id = None
        self.task_status = None
        self.running_port = None
        self.task_score = None




def create_task_table():  # 建表
    try:
        # cur.execute('drop table if EXISTS task')
        sql = "CREATE TABLE task (" \
              "id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY," \
              "task_id VARCHAR(36) NOT NULL," \
              "user_id VARCHAR(36) NOT NULL," \
              "task_status VARCHAR(10) NOT NULL," \
              "running_port INT," \
              "task_score FLOAT)"
        conn.ping(reconnect=True)
        cur.execute(sql)
        conn.commit()
    except Exception as e:
        # print('fail to create table: task, error: ', e)
        pass



def query_task(task_id):
    sql = "select task_id, user_id, task_status, task_score, running_port, cca_name, score_without_loss, score_with_loss from task where task_id = '%s'"
    param = (str(task_id))
    result = select(sql % param)
    if len(result) > 0:
        return result[0]
    return result

def update_task_status(task_id, task_status):
    sql = "update task set task_status = '%s' where task_id = '%s'"
    param = (task_status, str(task_id))
    update(sql % param)


def insert_task_item(task_id, user_id, task_status, created_time):
    sql = "insert into task(task_id, user_id, task_status, created_time) values('%s', '%s', '%s', '%s')"
    param = (str(task_id), str(user_id), task_status, created_time)
    insert(sql % param)