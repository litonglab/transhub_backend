from app.extensions import cur
from templates import conn, insert, select, update


class User_model:

    def __init__(self, user_id=None, username=None, password=None, alname=None, real_name=None, Sclass=None, sno=None):
        self.user_id = user_id
        self.username = username
        self.password = password
        self.Sno = sno
        self.Sclass = Sclass
        self.user_real_name = real_name
        self.alname = alname

    def get_user_dir(self):
        return ''.join(self.sno) + '_' + ''.join(self.username)


def create_user_table():  # 建表
    try:
        # cur.execute('drop table if EXISTS student')
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
        pass
        # print('fail to create table: student')

def query_user_by_sno(sno) -> User_model : # 查询学生信息
    sql = "SELECT * FROM student WHERE sno = '%s'" % sno
    result = select(sql)
    return User_model(result[0], result[1], result[2], result[3], result[4], result[5], result[6])


def query_user_by_id(user_id) -> User_model : # 查询学生信息
    sql = "SELECT * FROM student WHERE user_id = '%s'" % user_id
    result = select(sql)
    return User_model(result[0], result[1], result[2], result[3], result[4], result[5], result[6])

def insert_user_item(user_id, username, password, alname, real_name, Sclass, sno):  # 插入数据
    sql = "insert into student values('%s', '%s', '%s', '%s', '%s', '%s', '%s')"
    param = (str(user_id), str(username), str(password), str(alname), str(real_name), str(Sclass), str(sno))
    insert(sql % param)


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
