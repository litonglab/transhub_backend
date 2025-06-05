import os
import logging

from app_backend import db
from sqlalchemy.dialects.mysql import VARCHAR

logger = logging.getLogger(__name__)

class Task_model(db.Model):
    __tablename__ = 'task'
    task_id = db.Column(db.String(36), primary_key=True)
    upload_id = db.Column(db.String(36), nullable=False)  # 标识是哪次提交
    loss_rate = db.Column(db.Float, nullable=False)  # 标识运行的环境,loss_rate
    buffer_size = db.Column(db.Integer, nullable=False)  # 标识运行的环境,buffer_size
    trace_name = db.Column(db.String(50), nullable=False)  # 标识运行的trace
    user_id = db.Column(db.String(36), nullable=False)
    task_status = db.Column(db.String(10), nullable=False)
    created_time = db.Column(db.DateTime, nullable=False)
    # running_port = db.Column(db.Integer)
    task_score = db.Column(db.Float)
    cname = db.Column(VARCHAR(50, charset='utf8mb4'), nullable=False)
    # cname = db.Column(db.String(50))  # 任务类型，可以表示是哪个比赛的任务
    task_dir = db.Column(db.String(256))  # 任务的文件夹, 用于存放用户上传的文件
    algorithm = db.Column(db.String(50))  # 算法名称

    def __repr__(self):
        return f'<Task {self.task_id}>'

    def save(self):
        logger.debug(f"Saving task {self.task_id} for user {self.user_id}")
        db.session.add(self)
        db.session.commit()
        logger.info(f"Task {self.task_id} saved successfully")

    def update(self, **kwargs):
        logger.debug(f"Updating task {self.task_id} with parameters: {kwargs}")
        try:
            with db.session.begin_nested():
                for key, value in kwargs.items():
                    setattr(self, key, value)
                db.session.commit()
            logger.info(f"Task {self.task_id} updated successfully")
        except Exception as e:
            logger.error(f"Error updating task {self.task_id}: {str(e)}", exc_info=True)
            db.session.rollback()
            raise e

    def delete(self):
        logger.info(f"Deleting task {self.task_id}")
        db.session.delete(self)
        db.session.commit()
        logger.info(f"Task {self.task_id} deleted successfully")

    def to_detail_dict(self):

        if self.task_status == 'finished':
            res = {
                'user_id': self.user_id,
                'task_id': self.task_id,
                'upload_id': self.upload_id,
                'loss_rate': self.loss_rate,
                'buffer_size': self.buffer_size,
                'trace_name': self.trace_name,
                'task_status': self.task_status,
                'created_time': self.created_time.strftime("%Y-%m-%d %H:%M:%S"),
                'task_score': self.task_score,
                'cname': self.cname,
                'algorithm': self.algorithm,
                'log':"success"
            }
            return res

        elif self.task_status == 'running':
            res = {
                'user_id': self.user_id,
                'task_id': self.task_id,
                'upload_id': self.upload_id,
                'loss_rate': self.loss_rate,
                'buffer_size': self.buffer_size,
                'trace_name': self.trace_name,
                'task_status': self.task_status,
                'created_time': self.created_time.strftime("%Y-%m-%d %H:%M:%S"),
                'task_score': 0,
                'cname': self.cname,
                'algorithm': self.algorithm,
                'log':"running"
            }
            return res
        elif self.task_status == 'error':
            logpath = self.task_dir + '/error.log'
            log_content = ''
            if os.path.exists(logpath):
                with open(logpath, 'r') as f:
                    log_content = f.read()
                logger.error(f"Task {self.task_id} error log: {log_content}")
            else:
                logger.warning(f"Error log file not found for task {self.task_id} at {logpath}")
                
            res = {
                'user_id': self.user_id,
                'task_id': self.task_id,
                'upload_id': self.upload_id,
                'loss_rate': self.loss_rate,
                'buffer_size': self.buffer_size,
                'trace_name': self.trace_name,
                'task_status': self.task_status,
                'created_time': self.created_time.strftime("%Y-%m-%d %H:%M:%S"),
                'task_score': 0,
                'cname': self.cname,
                'algorithm': self.algorithm,
                'log': log_content
            }
            return res
        elif self.task_status == 'queued':
            res = {
                'user_id': self.user_id,
                'task_id': self.task_id,
                'upload_id': self.upload_id,
                'loss_rate': self.loss_rate,
                'buffer_size': self.buffer_size,
                'trace_name': self.trace_name,
                'task_status': self.task_status,
                'created_time': self.created_time.strftime("%Y-%m-%d %H:%M:%S"),
                'task_score': 0,
                'cname': self.cname,
                'algorithm': self.algorithm,
                'log': "queued"
            }
            return res


def to_history_dict(tasks: list):
    #将tasks按upload_id聚合,score求和。如果status有一个是error，则整体status是error，score是0，如果有一个是running，则整体是running，score是当前的score，否则是finished，score是求和的score
    res = []
    upload_id_set = set()

    for task in tasks:
        if task.upload_id not in upload_id_set:
            upload_id_set.add(task.upload_id)
            history = {
                "cname": task.cname,
                "algorithm": task.algorithm,
                "created_time": task.created_time,
                "status": task.task_status,
                "score": task.task_score,
                "upload_id": task.upload_id
            }
            res.append(history)
        else:
            for r in res:
                if r['upload_id'] == task.upload_id:
                    if task.task_status == 'error':
                        r['status'] = 'error'
                        r['score'] = 0
                    elif task.task_status == 'running' and r['status'] != 'error':
                        r['status'] = 'running'
                        r['score'] = task.task_score
                    elif r['status'] not in ['error', 'running']:
                        r['score'] += task.task_score

    return res

