from flask import session

from app_backend.model.Task_model import Task_model


def check_task_auth(user_id, task_id):
    task = Task_model.query.filter_by(task_id=task_id).first()
    if task.user_id != user_id:
        return False
    return True


def check_upload_auth(upload_id, user_id):
    task = Task_model.query.filter_by(upload_id=upload_id).first()
    if task.user_id != user_id:
        return False
    return True
