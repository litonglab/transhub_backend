import os

from flask import Blueprint, request, send_file
from flask_jwt_extended import get_jwt_identity, jwt_required

from app_backend.decorators.validators import validate_request
from app_backend.model.Task_model import Task_model
from app_backend.validators.schemas import SourceCodeSchema
from app_backend.vo import HttpResponse

source_code_bp = Blueprint('app_backend', __name__)


@source_code_bp.route("/src_get_code", methods=["POST"])
@jwt_required()
@validate_request(SourceCodeSchema)
def return_code():
    data = request.validated_data
    upload_id = data.upload_id
    user_id = get_jwt_identity()
    # Check if the user is authorized to access the task
    # 保证用户只能查询自己的任务
    task_info = Task_model.query.filter_by(upload_id=upload_id, user_id=user_id).first()

    file_path = task_info.task_dir + "/../" + task_info.algorithm + ".cc"
    if not os.path.exists(file_path):
        return HttpResponse.fail("File not found")
    return send_file(file_path, as_attachment=True, download_name=task_info.algorithm + ".cc")
