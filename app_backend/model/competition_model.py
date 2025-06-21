import logging

from sqlalchemy.dialects.mysql import VARCHAR

from app_backend import db

logger = logging.getLogger(__name__)


class CompetitionModel(db.Model):
    __tablename__ = 'competition'
    id = db.Column(db.Integer, primary_key=True)
    # cname = db.Column(db.String(30), nullable=False)
    cname = db.Column(VARCHAR(50, charset='utf8mb4'), nullable=False)
    user_id = db.Column(db.String(36), nullable=False)

    def save(self):
        logger.debug(f"Saving competition entry for user {self.user_id} in competition {self.cname}")
        db.session.add(self)
        db.session.commit()
        logger.info(f"Competition entry saved successfully for user {self.user_id} in {self.cname}")
