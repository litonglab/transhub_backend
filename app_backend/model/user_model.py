import hashlib
import logging
import os
import uuid
from enum import Enum

from sqlalchemy import func, text
from sqlalchemy.dialects.mysql import VARCHAR

from app_backend import db, get_default_config
from app_backend.model.competition_model import CompetitionModel

logger = logging.getLogger(__name__)
config = get_default_config()


class UserRole(Enum):
    """用户角色枚举"""
    STUDENT = "student"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


class UserModel(db.Model):
    __tablename__ = 'student'
    user_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = db.Column(VARCHAR(50, charset='utf8mb4'), nullable=False)
    password = db.Column(db.String(128), nullable=False)  # 增加长度以适应加密
    real_name = db.Column(VARCHAR(50, charset='utf8mb4'), nullable=False)
    sno = db.Column(db.String(20), nullable=False)
    role = db.Column(db.Enum(UserRole), nullable=False, server_default=UserRole.STUDENT.value)
    is_locked = db.Column(db.Boolean, nullable=False, server_default=text("0"))
    is_deleted = db.Column(db.Boolean, nullable=False, server_default=text("0"))
    created_at = db.Column(db.DateTime, server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, server_default=func.now(),
                           onupdate=func.now(), nullable=False)

    def set_password(self, raw_password):
        self.password = hashlib.sha256(raw_password.encode('utf-8')).hexdigest()

    def check_password(self, raw_password):
        return self.password == hashlib.sha256(raw_password.encode('utf-8')).hexdigest()

    def save(self):
        logger.debug(f"Saving user: {self.username}")
        try:
            db.session.add(self)
            db.session.commit()
            logger.info(f"User saved successfully: {self.username}")
        except Exception as e:
            logger.error(f"Error saving user {self.username}: {str(e)}", exc_info=True)
            db.session.rollback()
            raise

    def is_admin(self) -> bool:
        """检查用户是否为管理员"""
        return self.role in [UserRole.ADMIN, UserRole.SUPER_ADMIN]

    def is_super_admin(self) -> bool:
        """检查用户是否为超级管理员"""
        return self.role == UserRole.SUPER_ADMIN

    def to_dict(self):
        """转换为字典，包含角色信息"""
        return {
            'user_id': self.user_id,
            'username': self.username,
            'real_name': self.real_name,
            'sno': self.sno,
            'role': self.role.value,  # 将枚举转换为字符串值
            'is_locked': self.is_locked,
            'is_deleted': self.is_deleted,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }

    def is_active(self) -> bool:
        """检查用户是否为活跃状态（未删除且未锁定）"""
        return not self.is_deleted and not self.is_locked

    def get_user_dir(self, cname):
        """
        获取用户目录
        :param cname: 比赛名称
        :return: 可以直接使用的全局路径
        """
        logger.debug(f"Getting user directory for user {self.username} and competition {cname}")
        _dir = os.path.join(config.App.USER_DIR_PATH, self.username + "_" + self.sno,
                            config.get_course_config(cname)["name"])
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
        # user_name is unique, sno is unique (只检查未删除的用户)
        if UserModel.query.filter_by(username=self.username, is_deleted=False).first():
            logger.warning(f"User with username {self.username} already exists.")
            return True
        elif UserModel.query.filter_by(sno=self.sno, is_deleted=False).first():
            logger.warning(f"User with sno {self.sno} already exists, but username {self.username} is not unique.")
            return True
        return False

    @staticmethod
    def get_active_users():
        """获取所有活跃用户（未删除）"""
        return UserModel.query.filter_by(is_deleted=False)

    @staticmethod
    def get_deleted_users():
        """获取所有已删除的用户"""
        return UserModel.query.filter_by(is_deleted=True)

    def update_real_info(self, real_name):
        logger.debug(f"Updating real name for user {self.username} to: {real_name}")
        try:
            self.real_name = real_name
            db.session.commit()
            logger.info(f"Real name updated successfully for user {self.username}")
        except Exception as e:
            logger.error(f"Error updating real name for user {self.username}: {str(e)}", exc_info=True)
            db.session.rollback()
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
            try:
                com.save()
                logger.info(f"User {self.username} successfully participated in competition {cname}")
                return True
            except Exception as e:
                logger.error(f"Error participating in competition for user {self.username}: {str(e)}", exc_info=True)
                db.session.rollback()
                raise

    def lock(self):
        logger.debug(f"Locking user: {self.username}")
        try:
            self.is_locked = True
            db.session.commit()
            logger.info(f"User {self.username} locked successfully")
        except Exception as e:
            logger.error(f"Error locking user {self.username}: {str(e)}", exc_info=True)
            db.session.rollback()
            raise

    def unlock(self):
        logger.debug(f"Unlocking user: {self.username}")
        try:
            self.is_locked = False
            db.session.commit()
            logger.info(f"User {self.username} unlocked successfully")
        except Exception as e:
            logger.error(f"Error unlocking user {self.username}: {str(e)}", exc_info=True)
            db.session.rollback()
            raise

    def reset_password(self, new_password="123456"):
        """重置用户密码（加密存储）"""
        logger.debug(f"Resetting password for user: {self.username}")
        try:
            self.set_password(new_password)
            db.session.commit()
            logger.info(f"Password reset successfully for user {self.username}")
            return True
        except Exception as e:
            logger.error(f"Error resetting password for user {self.username}: {str(e)}", exc_info=True)
            db.session.rollback()
            raise

    def soft_delete(self):
        """软删除用户"""
        logger.debug(f"Soft deleting user: {self.username}")
        try:
            self.is_deleted = True
            # 软删除时同时锁定账户
            self.is_locked = True
            db.session.commit()
            logger.info(f"User {self.username} soft deleted successfully")
        except Exception as e:
            logger.error(f"Error soft deleting user {self.username}: {str(e)}", exc_info=True)
            db.session.rollback()
            raise

    def restore(self):
        """恢复被软删除的用户"""
        logger.debug(f"Restoring user: {self.username}")

        # 检查是否已有同名的活跃用户
        existing_user = UserModel.query.filter_by(username=self.username, is_deleted=False).first()
        if existing_user and existing_user.user_id != self.user_id:
            logger.warning(f"Cannot restore user {self.username}: username already exists")
            raise ValueError(f"用户名 {self.username} 已被占用，无法恢复该用户")
        try:
            self.is_deleted = False
            # 恢复时解锁账户
            self.is_locked = False
            db.session.commit()
            logger.info(f"User {self.username} restored successfully")
        except Exception as e:
            logger.error(f"Error restoring user {self.username}: {str(e)}", exc_info=True)
            db.session.rollback()
            raise

    def get_id(self):
        return self.user_id
