

from app.extensions import db



class Task_model(db.Model):
    __tablename__ = 'task'
    task_id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(36), nullable=False)
    task_status = db.Column(db.String(10), nullable=False)
    created_time = db.Column(db.DateTime, nullable=False)
    running_port = db.Column(db.Integer)
    task_score = db.Column(db.Float)
    task_type = db.Column(db.String(10))

    def __repr__(self):
        return f'<Task {self.task_id}>'

    def save(self):
        db.session.add(self)
        db.session.commit()

    def update(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
        db.session.commit()

    def delete(self):
        db.session.delete(self)
        db.session.commit()

