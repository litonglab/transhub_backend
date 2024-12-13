
from flask import session

from app_backend.model.Task_model import Task_model




def check_user_state(user_id):
    if user_id != session.get('user_id'):
        return False
    return True

def check_task_auth(user_id, task_id):
    if not check_user_state(user_id):
        return False
    task = Task_model.query.filter_by(task_id=task_id).first()
    if task.user_id != user_id:
        return False
    return True

def check_upload_auth(upload_id,user_id):
    if not check_user_state(user_id):
        return False
    task = Task_model.query.filter_by(upload_id=upload_id).first()
    if task.user_id != user_id:
        return False
    return True
