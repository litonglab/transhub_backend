from app.extensions import db


class Task_model(db.Model):
    __tablename__ = 'task'
    task_id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(36), nullable=False)
    task_status = db.Column(db.String(10), nullable=False)
    created_time = db.Column(db.DateTime, nullable=False)
    running_port = db.Column(db.Integer)
    task_score = db.Column(db.Float)
    cname = db.Column(db.String(50))  # 任务类型，可以表示是哪个比赛的任务
    task_dir = db.Column(db.String(256))  # 任务的文件夹, 用于存放用户上传的文件
    algorithm = db.Column(db.String(50))  # 算法名称

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

    def to_history_dict(self):
        return {
            'task_id': self.task_id,
            'user_id': self.user_id,
            'task_status': self.task_status,
            'created_time': self.created_time,
            'running_port': self.running_port,
            'task_score': self.task_score,
            'cname': self.cname,
            'algorithm': self.algorithm}
