import logging
import os

from flask import Blueprint
from flask_jwt_extended import get_jwt_identity, jwt_required

from app_backend.model.task_model import TaskModel
from app_backend.validators.decorators import validate_request, get_validated_data
from app_backend.validators.schemas import SourceCodeSchema
from app_backend.vo.http_response import HttpResponse

source_code_bp = Blueprint('app_backend', __name__)
logger = logging.getLogger(__name__)


@source_code_bp.route("/src_get_code", methods=["POST"])
@jwt_required()
@validate_request(SourceCodeSchema)
def return_code():
    data = get_validated_data(SourceCodeSchema)
    upload_id = data.upload_id
    user_id = get_jwt_identity()
    logger.debug(f"Source code request for upload {upload_id} by user {user_id}")

    # Check if the user is authorized to access the task
    # 保证用户只能查询自己的任务
    task_info = TaskModel.query.filter_by(upload_id=upload_id, user_id=user_id).first()
    if not task_info:
        logger.warning(f"Source code request failed: Task not found for upload {upload_id} and user {user_id}")
        return HttpResponse.fail("Task not found")

    file_path = task_info.task_dir + "/../" + task_info.algorithm + ".cc"
    if not os.path.exists(file_path):
        logger.warning(f"Source code file not found: {file_path}")
        return HttpResponse.fail("File not found")

    logger.info(f"Sending source code file: {file_path}")
    return HttpResponse.send_attachment_file(file_path)
