import logging

from sqlalchemy import func
from sqlalchemy.dialects.mysql import VARCHAR

from app_backend import db

logger = logging.getLogger(__name__)


class CompetitionModel(db.Model):
    __tablename__ = 'competition'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    cname = db.Column(VARCHAR(50, charset='utf8mb4'), nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey('student.user_id'), nullable=False)
    created_at = db.Column(db.DateTime, server_default=func.now(), nullable=False)

    def save(self):
        logger.debug(f"Saving competition entry for user {self.user_id} in competition {self.cname}")
        try:
            db.session.add(self)
            db.session.commit()
            logger.info(f"Competition entry saved successfully for user {self.user_id} in {self.cname}")
        except Exception as e:
            logger.error(f"Error saving competition entry for user {self.user_id} in {self.cname}: {str(e)}",
                         exc_info=True)
            db.session.rollback()
            raise
