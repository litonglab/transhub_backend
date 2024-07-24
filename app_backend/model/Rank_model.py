from app_backend import db


class Rank_model(db.Model):
    __tablename__ = 'rank'
    task_id = db.Column(db.String(36), primary_key=False)  # their newest task's task_id
    user_id = db.Column(db.String(36), primary_key=True)
    task_score = db.Column(db.Float, nullable=False)
    algorithm = db.Column(db.String(50), nullable=False)
    upload_time = db.Column(db.DateTime, nullable=False)

    def update(self, **kwargs):
        try:
            with db.session.begin_nested():
                for key, value in kwargs.items():
                    setattr(self, key, value)
                db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e

    def insert(self):
        db.session.add(self)
        db.session.commit()

    def to_dict(self):
        return {
            'task_id': self.task_id,
            'user_id': self.user_id,
            'task_score': self.task_score,
            'algorithm': self.algorithm,
            'upload_time': self.upload_time
        }