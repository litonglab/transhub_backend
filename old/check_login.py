from templates import conn, pool, select, insert, update


cur = conn.cursor()
ALL_CLASS = ["计算机系统基础II", "计算机网络"]


def create_task_table():  # 建表
    try:
        cur.execute('drop table if EXISTS task')
        sql = "create table task(" \
              "id int unsigned auto_increment," \
              "task_id varchar(36) not null," \
              "user_id varchar(36) not null," \
              "task_status varchar(10) not null," \
              "running_port int," \
              "task_score float)"
        conn.ping(reconnect=True)
        cur.execute(sql)
        conn.commit()
    except:
        print('fail to create table: task')


def insert_task_item(task_id, user_id, task_status, created_time):
    sql = "insert into task(task_id, user_id, task_status, created_time) values('%s', '%s', '%s', '%s')"
    param = (str(task_id), str(user_id), task_status, created_time)
    insert(sql % param)


def query_rank_list(Sclass=None):
    # sql = "select * from(select @rn:= CASE when @user_id = user_id then @rn + 1 else 1 end as rn, @user_id:=
    # user_id as user_id, task_score, task_status, created_time  from (select * from task where task_score is not
    # null order by user_id, created_time desc) a, (select @rn=0, @user_id=0) b) c where rn <= 1;"
    if Sclass:
        sql = "select task_id,task.user_id,student.username,cca_name, task_score,created_time, score_without_loss, score_with_loss from student,task,(select max(task_score) as mscore , task.user_id as uid from task where task.task_score is not null group by task.user_id) as temp where task.user_id = uid and task.task_score = mscore and task.user_id = student.user_id and student.Sclass = '%s' order by task_score desc;" % str(
            Sclass)
    # sql = "select task_id,task.user_id,student.username,cca_name, task_score,created_time, score_without_loss, score_with_loss from student,task,(select max(created_time) as ctime , task.user_id as uid from task where task.task_score is not null group by task.user_id, task.cca_name) as temp where task.user_id = uid and task.created_time = ctime and task.user_id = student.user_id and student.Sclass = '%s' order by task_score desc, created_time asc;"  % str(Sclass)
    else:
        exclude_str = [" and student.Sclass != '%s' " % temp for temp in ALL_CLASS]
        sql = "select task_id,task.user_id,student.username,cca_name, task_score,created_time, score_without_loss, score_with_loss from student,task,(select max(created_time) as ctime , task.user_id as uid from task where task.task_score is not null group by task.user_id, task.cca_name) as temp where task.user_id = uid and task.created_time = ctime and task.user_id = student.user_id  {} order by task_score desc, created_time asc;".format(
            "".join(exclude_str))
        print(sql)
    result = select(sql)
    return result


def query_history_records(user_id):
    sql = "select task_id, user_id, task_status, task_score, running_port, cca_name, created_time, score_without_loss, score_with_loss from task where user_id = '%s' order by created_time desc"
    param = (str(user_id))
    result = select(sql % param)
    return result


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


def create_user_table():  # 建表
    try:
        cur.execute('drop table if EXISTS student')
        sql = "create table student(" \
              "user_id varchar(36) not null," \
              "username varchar(30) not null," \
              "password varchar(30) not null," \
              "alname varchar(50) not null," \
              "real_name varchar(50) not null," \
              "Sclass varchar(30) not null," \
              "sno char(11) not null)"
        conn.ping(reconnect=True)
        cur.execute(sql)
        conn.commit()
    except:
        print('fail to create table: student')


def insert_user_item(user_id, username, password, alname, real_name, Sclass, sno):  # 插入数据
    sql = "insert into student values('%s', '%s', '%s', '%s', '%s', '%s', '%s')"
    param = (str(user_id), str(username), str(password), str(alname), str(real_name), str(Sclass), str(sno))
    insert(sql % param)


def change_user_item(user_id, password):  # 修改数据
    sql = "update student set password = '%s' where user_id = '%s'"
    param = (password, str(user_id))
    update(sql % param)


def is_null(username, password):  # 检查用户名或密码是否为空
    if username == '' or password == '':
        return True
    else:
        return False


def is_null_info(real_name, sno, Sclass):
    if real_name == '' or sno == '' or Sclass == '':
        return True
    else:
        return False


def is_existed(username, password):  # 检查该学生是否在数据表中
    sql = "SELECT * FROM student WHERE username ='%s' and password ='%s'" % (username, password)
    result = select(sql)
    if len(result) == 0:
        return False
    else:
        return True


def query_user(username, password):  # 检查该学生是否在数据表中
    sql = "SELECT user_id FROM student WHERE username ='%s' and password ='%s'" % (username, password)
    result = select(sql)
    print(result[0][0])
    return result[0][0]


def query_real_info(user_id):  # 查询学生真实信息
    sql = "SELECT real_name, Sclass, sno FROM student WHERE user_id = '%s'" % user_id
    result = select(sql)
    return result[0]


def update_real_info(user_id, real_name, Sclass, sno):
    sql = "update student set real_name = '%s', Sclass = '%s', sno = '%s' where user_id = '%s'"
    param = (str(real_name), str(Sclass), str(sno), str(user_id))
    update(sql % param)


def query_pwd(user_id):  # 查询学生密码
    sql = "SELECT password FROM student WHERE user_id = '%s'" % user_id
    result = select(sql)
    return result


def exist_user(username):  # 检查用户名是否存在
    sql = "SELECT * FROM student WHERE username ='%s'" % (username)
    result = select(sql)
    if len(result) == 0:
        return False
    else:
        return True
