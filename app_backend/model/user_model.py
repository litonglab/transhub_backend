import logging
import os

from sqlalchemy.dialects.mysql import VARCHAR

from app_backend import db, get_default_config
from app_backend.model.competition_model import CompetitionModel

logger = logging.getLogger(__name__)
config = get_default_config()


class UserModel(db.Model):
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
        _dir = os.path.join(config.App.USER_DIR_PATH, self.username + "_" + self.sno,
                            config.Course.ALL_CLASS[cname]["name"])
        if not os.path.exists(_dir):
            logger.info(f"Creating user directory: {_dir}")
            os.makedirs(_dir)
        return _dir

    def save_file_to_user_dir(self, file, cname, upload_dir_name):
        logger.debug(f"Saving file {file.filename} for user {self.username} in competition {cname}")
        user_dir = self.get_user_dir(cname)

        if not os.path.exists(user_dir):
            logger.info(f"Creating user directory: {user_dir}")
            os.makedirs(user_dir)

        # 由当前时间生成文件夹
        filedir = f"{user_dir}/{upload_dir_name}"
        if not os.path.exists(filedir):
            logger.info(f"Creating file directory: {filedir}")
            os.makedirs(filedir)

        file_path = os.path.join(filedir, file.filename)
        logger.debug(f"Saving file to: {file_path}")
        file.save(file_path)
        logger.info(f"File saved successfully: {file_path}")
        return filedir

    def is_exist(self) -> bool:
        logger.debug(f"Checking if user exists: {self.username} with sno {self.sno}")
        # user_name is unique, sno is unique
        if UserModel.query.filter_by(username=self.username).first():
            logger.warning(f"User with username {self.username} already exists.")
            return True
        elif UserModel.query.filter_by(sno=self.sno).first():
            logger.warning(f"User with sno {self.sno} already exists, but username {self.username} is not unique.")
            return True
        return False

    def update_real_info(self, real_name):
        logger.debug(f"Updating real name for user {self.username} to: {real_name}")
        try:
            self.real_name = real_name
            db.session.commit()
            logger.info(f"Real name updated successfully for user {self.username}")
        except Exception as e:
            logger.error(f"Error updating real name for user {self.username}: {str(e)}", exc_info=True)
            raise

    def participate_competition(self, cname) -> bool:
        logger.info(f"User {self.username} attempting to participate in competition: {cname}")
        # 1. 参赛
        if CompetitionModel.query.filter_by(user_id=self.user_id, cname=cname).first():
            logger.info(f"User {self.username} already participating in competition {cname}")
            return True
        else:
            logger.debug(f"Creating new competition entry for user {self.username}")
            com = CompetitionModel(user_id=self.user_id, cname=cname)
            # 2. create user directory
            user_dir = self.get_user_dir(cname)  # 用户目录下的竞赛目录下的竞赛文件目录
            if not os.path.exists(user_dir):
                logger.info(f"Creating work directory: {user_dir}")
                os.makedirs(user_dir)
            # 由于已经改为公共目录编译，不再需要生成用户目录下的编译目录，简化代码逻辑
            com.save()
            logger.info(f"User {self.username} successfully participated in competition {cname}")
            return True

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
