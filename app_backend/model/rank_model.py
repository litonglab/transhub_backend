import logging
import uuid

from sqlalchemy import func
from sqlalchemy.dialects.mysql import VARCHAR

from app_backend import db

logger = logging.getLogger(__name__)


class RankModel(db.Model):
    __tablename__ = 'rank'
    rank_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    upload_id = db.Column(db.String(36), nullable=False)  # their newest upload's upload_id, 后续upload应单独建表
    user_id = db.Column(db.String(36), db.ForeignKey('student.user_id'),
                        default=lambda: str(uuid.uuid4()))
    task_score = db.Column(db.Float, nullable=False)
    algorithm = db.Column(db.String(50), nullable=False)
    upload_time = db.Column(db.DateTime, nullable=False)
    cname = db.Column(VARCHAR(50, charset='utf8mb4'), nullable=False)  # 后续修改相关查询逻辑后可删除
    competition_id = db.Column(db.Integer, db.ForeignKey('competition.id'), nullable=False)
    username = db.Column(VARCHAR(50, charset='utf8mb4'), nullable=False)
    created_at = db.Column(db.DateTime, server_default=func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        server_default=func.now(),
        server_onupdate=func.now(),
        nullable=False
    )

    def update(self, **kwargs):
        logger.debug(f"Updating rank for user {self.username} with parameters: {kwargs}")
        try:
            with db.session.begin_nested():
                for key, value in kwargs.items():
                    setattr(self, key, value)
                db.session.commit()
            logger.info(f"Rank updated successfully for user {self.username}")
        except Exception as e:
            logger.error(f"Error updating rank for user {self.username}: {str(e)}", exc_info=True)
            db.session.rollback()
            raise e

    def insert(self):
        logger.debug(f"Inserting new rank for user {self.username}")
        try:
            db.session.add(self)
            db.session.commit()
            logger.info(f"Rank inserted successfully for user {self.username}")
        except Exception as e:
            logger.error(f"Error inserting rank for user {self.username}: {str(e)}", exc_info=True)
            db.session.rollback()
            raise

    def to_dict(self):
        return {
            'upload_id': self.upload_id,
            'username': self.username,
            'task_score': self.task_score,
            'algorithm': self.algorithm,
            'upload_time': self.upload_time,
            'created_at': self.created_at,
            'updated_at': self.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
