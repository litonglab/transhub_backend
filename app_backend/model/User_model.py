from app_backend.config import USER_DIR_PATH, ALL_CLASS_PATH, ALL_CLASS
from app_backend import db
import os

from app_backend.model.Competition_model import Competition_model


class User_model(db.Model):
    __tablename__ = 'student'
    user_id = db.Column(db.String(36), primary_key=True)
    username = db.Column(db.String(30), nullable=False)
    password = db.Column(db.String(64), nullable=False)
    real_name = db.Column(db.String(50), nullable=False)
    sno = db.Column(db.String(20), nullable=False)
    is_locked = db.Column(db.Boolean, default=False)  # 编译时使用，保证编译安全

    def save(self):
        db.session.add(self)
        db.session.commit()

    def get_user_dir(self, cname):
        """

        :param cname:
        :return: 可以直接使用的全局路径
        """
        dir = USER_DIR_PATH + "/" + self.username + "_" + self.sno + "/" + ALL_CLASS[cname]
        if not os.path.exists(dir):
            os.makedirs(dir)
        return dir

    def save_file_to_user_dir(self, file, cname, nowtime):
        user_dir = self.get_user_dir(cname)

        if not os.path.exists(user_dir):
            os.makedirs(user_dir)
        # 由当前时间生成文件夹
        filedir = user_dir + "/" + nowtime
        if not os.path.exists(filedir):
            os.makedirs(filedir)
        file.save(filedir + "/" + file.filename)

    def is_exist(self) -> bool:
        # user_name is unique, sno is unique
        user = User_model.query.filter_by(username=self.username)
        if user.first():
            return True
        return False

    def is_null_info(self):
        if self.real_name == '' or self.sno == '' or self.real_name == '' or self.sno == '':
            return True
        else:
            return False

    def update_real_info(self, real_name, sno):
        self.real_name = real_name
        self.sno = sno
        db.session.commit()

    def paticapate_competition(self, cname) -> bool:
        # 1. 参赛
        if Competition_model.query.filter_by(user_id=self.user_id, cname=cname).first():
            return True
        else:
            com = Competition_model(user_id=self.user_id, cname=cname)
            # 2. get competition dir and workdir
            com_dir = ALL_CLASS_PATH[cname]
            work_dir = self.get_competition_project_dir(cname)  # 用户目录下的竞赛目录下的竞赛文件目录
            if not os.path.exists(work_dir):
                os.makedirs(work_dir)
            # 3. run competion's init script
            cmd = f'bash {com_dir}/init/gen_test.sh {com_dir}/project {work_dir} && exit 0'
            try:
                os.system(cmd)
                com.save()
                return True
            except Exception as e:
                print(f"run init script error: {e}")
                return False

    def get_competition_project_dir(self, cname):
        """
        获取用户参赛的项目目录下的竞赛文件目录，每个用户的每个竞赛项目目录只会有一个竞赛文件目录，因此每个用户只能串行编译
        :param cname:
        :return: dirpath
        """
        return self.get_user_dir(cname) + "/project"

    def lock(self):
        self.is_locked = True
        db.session.commit()

    def unlock(self):
        self.is_locked = False
        db.session.commit()
