
from flask import session

from app.model.Task_model import Task_model

from app.model.User_model import User_model


def check_user_state(user_id):
    if user_id != session.get('user_id'):
        return False
    return True

def check_task_auth(user_id, task_id):
    if not check_user_state(user_id):
        return False
    task = Task_model.query.get(task_id)
    user = User_model.query.get(user_id)
    if task.user_id != user.user_id:
        return False
    return True
