import os

from app_backend import db


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
        try:
            with db.session.begin_nested():
                for key, value in kwargs.items():
                    setattr(self, key, value)
                db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e

    def delete(self):
        db.session.delete(self)
        db.session.commit()

    def to_detail_dict(self):
        trace2score = {}
        from app_backend.jobs.cctraing_job import evaluate_score
        from app_backend.config import cctraining_config
        score_dir = self.task_dir
        trace_dir = cctraining_config.uplink_dir
        total_trace = 0
        total_score = 0

        for trace_file in os.listdir(trace_dir):
            total_trace += 1
            trace_score_file_path = score_dir + "/" + trace_file + ".score"
            if os.path.exists(trace_score_file_path):
                score = evaluate_score(self, trace_score_file_path)
                total_score += score
                # 获取trace名字
                trace_name = trace_file.split('.')[0]
                trace2score[trace_name] = score

        # 逻辑是读取所有的

        if self.task_status == 'finished':
            res = {
                'user_id': self.user_id,
                'task_id': self.task_id,
                'task_status': self.task_status,
                'created_time': self.created_time.strftime("%Y-%m-%d %H:%M:%S"),
                'running_port': self.running_port,
                'task_score': total_score,
                'cname': self.cname,
                'algorithm': self.algorithm,
                'trace_score': trace2score
            }
            if self.task_score == 0:
                self.update(task_score=total_score)
            return res

        elif self.task_status == 'running':
            res = {
                'user_id': self.user_id,
                'task_id': self.task_id,
                'task_status': self.task_status,
                'created_time': self.created_time.strftime("%Y-%m-%d %H:%M:%S"),
                'running_port': self.running_port,
                'cname': self.cname,
                'algorithm': self.algorithm,
                'trace_score': trace2score
            }
            self.update(task_score=total_score)
            return res

    def to_history_dict(self):
        res = {
            'user_id': self.user_id,
            'task_id': self.task_id,
            'task_status': self.task_status,
            'created_time': self.created_time.strftime("%Y-%m-%d %H:%M:%S"),
            'cname': self.cname,
            'algorithm': self.algorithm,
            'score':self.task_score
        }
        return res
