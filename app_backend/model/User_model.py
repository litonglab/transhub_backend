import os
import logging

from sqlalchemy.dialects.mysql import VARCHAR

from app_backend import db
from app_backend.config import USER_DIR_PATH, ALL_CLASS
from app_backend.model.Competition_model import Competition_model

logger = logging.getLogger(__name__)

class User_model(db.Model):
    __tablename__ = 'student'
    user_id = db.Column(db.String(36), primary_key=True)
    # username = db.Column(db.String(30), nullable=False)
    username = db.Column(VARCHAR(50, charset='utf8mb4'), nullable=False)
    password = db.Column(db.String(64), nullable=False)
    # real_name = db.Column(db.String(50), nullable=False)
    real_name = db.Column(VARCHAR(50, charset='utf8mb4'), nullable=False)
    sno = db.Column(db.String(20), nullable=False)

    def save(self):
        logger.debug(f"Saving user: {self.username}")
        try:
            db.session.add(self)
            db.session.commit()
            logger.info(f"User saved successfully: {self.username}")
        except Exception as e:
            logger.error(f"Error saving user {self.username}: {str(e)}", exc_info=True)
            raise

    def get_user_dir(self, cname):
        """
        获取用户目录
        :param cname: 比赛名称
        :return: 可以直接使用的全局路径
        """
        logger.debug(f"Getting user directory for user {self.username} and competition {cname}")
        _dir = os.path.join(USER_DIR_PATH, self.username + "_" + self.sno, ALL_CLASS[cname]["name"])
        if not os.path.exists(_dir):
            logger.info(f"Creating user directory: {_dir}")
            os.makedirs(_dir)
        return _dir

    def save_file_to_user_dir(self, file, cname, nowtime):
        logger.debug(f"Saving file {file.filename} for user {self.username} in competition {cname}")
        user_dir = self.get_user_dir(cname)

        if not os.path.exists(user_dir):
            logger.info(f"Creating user directory: {user_dir}")
            os.makedirs(user_dir)
        
        # 由当前时间生成文件夹
        filedir = user_dir + "/" + nowtime
        if not os.path.exists(filedir):
            logger.info(f"Creating file directory: {filedir}")
            os.makedirs(filedir)
        
        file_path = filedir + "/" + file.filename
        logger.debug(f"Saving file to: {file_path}")
        file.save(file_path)
        logger.info(f"File saved successfully: {file_path}")

    def is_exist(self) -> bool:
        logger.debug(f"Checking if user exists: {self.username}")
        # user_name is unique, sno is unique
        user = User_model.query.filter_by(username=self.username)
        if user.first():
            return True
        return False

    def is_null_info(self):
        logger.debug(f"Checking if user info is null for user: {self.username}")
        is_null = self.real_name == '' or self.sno == '' or self.real_name == '' or self.sno == ''
        logger.debug(f"User info null check result: {is_null}")
        return is_null

    def update_real_info(self, real_name):
        logger.debug(f"Updating real name for user {self.username} to: {real_name}")
        try:
            self.real_name = real_name
            db.session.commit()
            logger.info(f"Real name updated successfully for user {self.username}")
        except Exception as e:
            logger.error(f"Error updating real name for user {self.username}: {str(e)}", exc_info=True)
            raise

    def paticapate_competition(self, cname) -> bool:
        logger.info(f"User {self.username} attempting to participate in competition: {cname}")
        # 1. 参赛
        if Competition_model.query.filter_by(user_id=self.user_id, cname=cname).first():
            logger.info(f"User {self.username} already participating in competition {cname}")
            return True
        else:
            logger.debug(f"Creating new competition entry for user {self.username}")
            com = Competition_model(user_id=self.user_id, cname=cname)
            # 2. get competition dir and workdir
            com_dir = ALL_CLASS[cname]["path"]
            work_dir = self.get_competition_project_dir(cname)  # 用户目录下的竞赛目录下的竞赛文件目录
            if not os.path.exists(work_dir):
                logger.info(f"Creating work directory: {work_dir}")
                os.makedirs(work_dir)
            # 3. run competion's init script
            cmd = f'bash {com_dir}/init/gen_test.sh {com_dir}/project {work_dir} && exit 0'
            try:
                logger.debug(f"Running initialization script: {cmd}")
                ret = os.system(cmd)
                if ret != 0:
                    logger.error(f"Initialization script failed with return code: {ret}")
                    return False
                com.save()
                logger.info(f"Competition {cname} initialized successfully for user {self.username}")
                return True
            except Exception as e:
                logger.error(f"Error running initialization script: {str(e)}", exc_info=True)
                return False

    def get_competition_project_dir(self, cname):
        """
        获取用户参赛的项目目录下的竞赛文件目录，每个用户的每个竞赛项目目录只会有一个竞赛文件目录，因此每个用户只能串行编译
        :param cname: 比赛名称
        :return: dirpath
        """
        return self.get_user_dir(cname) + "/project"

    def lock(self):
        logger.debug(f"Locking user: {self.username}")
        try:
            self.is_locked = True
            db.session.commit()
            logger.info(f"User {self.username} locked successfully")
        except Exception as e:
            logger.error(f"Error locking user {self.username}: {str(e)}", exc_info=True)
            raise

    def unlock(self):
        logger.debug(f"Unlocking user: {self.username}")
        try:
            self.is_locked = False
            db.session.commit()
            logger.info(f"User {self.username} unlocked successfully")
        except Exception as e:
            logger.error(f"Error unlocking user {self.username}: {str(e)}", exc_info=True)
            raise

    def get_id(self):
        return self.user_id
