import logging
import uuid

from sqlalchemy import func

from app_backend import db

logger = logging.getLogger(__name__)


class GraphModel(db.Model):
    __tablename__ = 'graph'
    graph_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = db.Column(db.String(36), db.ForeignKey('task.task_id'))
    # user_id = db.Column(db.String(36), primary_key=False)
    graph_type = db.Column(db.String(20), nullable=False)  # throughput, delay
    graph_path = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    def update(self, **kwargs):
        logger.debug(f"Updating graph {self.graph_id} for task {self.task_id} with parameters: {kwargs}")
        try:
            with db.session.begin_nested():
                for key, value in kwargs.items():
                    setattr(self, key, value)
                db.session.commit()
            logger.info(f"Graph {self.graph_id} updated successfully")
        except Exception as e:
            logger.error(f"Error updating graph {self.graph_id}: {str(e)}", exc_info=True)
            db.session.rollback()
            raise e

    def insert(self):
        logger.debug(f"Inserting new graph {self.graph_id} for task {self.task_id}")
        try:
            db.session.add(self)
            db.session.commit()
            logger.info(f"Graph {self.graph_id} inserted successfully")
        except Exception as e:
            logger.error(f"Error inserting graph {self.graph_id}: {str(e)}", exc_info=True)
            db.session.rollback()
            raise
