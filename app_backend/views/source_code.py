import os

from flask import Blueprint, request, send_file
from app_backend.security.safe_check import check_user_state, check_task_auth
from app_backend.model.Task_model import Task_model
from app_backend.vo.response import myResponse

source_code_bp = Blueprint('app_backend', __name__)


@source_code_bp.route("/src_get_code", methods=["POST"])
def return_code():
    task_id = request.json.get('upload_id')
    user_id = request.json.get('user_id')
    if (not check_task_auth(user_id, task_id)) or (not check_user_state(user_id)):
        return myResponse(400, "Please login firstly!")
    task_info = Task_model.query.filter_by(task_id=task_id).first()
    file_path = task_info.task_dir + "/" + task_info.algorithm + ".cc"
    if not os.path.exists(file_path):
        return myResponse(400, "File not found")
    return send_file(file_path, as_attachment=True)
