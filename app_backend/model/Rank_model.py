import logging

from app_backend import db
from sqlalchemy.dialects.mysql import VARCHAR

logger = logging.getLogger(__name__)

class Rank_model(db.Model):
    __tablename__ = 'rank'
    upload_id = db.Column(db.String(36), primary_key=False)  # their newest upload's upload_id
    user_id = db.Column(db.String(36), primary_key=True)
    task_score = db.Column(db.Float, nullable=False)
    algorithm = db.Column(db.String(50), nullable=False)
    upload_time = db.Column(db.DateTime, nullable=False)
    cname = db.Column(VARCHAR(50, charset='utf8mb4'), nullable=False)
    username = db.Column(VARCHAR(50, charset='utf8mb4'), nullable=False)

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
        db.session.add(self)
        db.session.commit()
        logger.info(f"Rank inserted successfully for user {self.username}")

    def to_dict(self):
        return {
            'upload_id': self.upload_id,
            'username': self.username,
            'task_score': self.task_score,
            'algorithm': self.algorithm,
            'upload_time': self.upload_time
        }