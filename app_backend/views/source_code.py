import logging
import os

from flask import Blueprint
from flask_jwt_extended import get_jwt_identity, jwt_required, current_user

from app_backend.model.task_model import TaskModel
from app_backend.validators.decorators import validate_request, get_validated_data
from app_backend.validators.schemas import SourceCodeSchema
from app_backend.vo.http_response import HttpResponse

source_code_bp = Blueprint('app_backend', __name__)
logger = logging.getLogger(__name__)


@source_code_bp.route("/src_get_code", methods=["GET"])
@jwt_required()
@validate_request(SourceCodeSchema)
def return_code():
    data = get_validated_data(SourceCodeSchema)
    upload_id = data.upload_id
    user_id = get_jwt_identity()
    logger.debug(f"Source code request for upload {upload_id} by user {user_id}")

    # Check if the user is authorized to access the task
    # 普通用户只能查询自己的任务，管理员可以查询所有任务
    if current_user and current_user.is_admin():
        # 管理员可以查看所有任务的源代码
        task_info = TaskModel.query.filter_by(upload_id=upload_id).first()
        logger.debug(f"Admin {current_user.username} accessing source code for upload {upload_id}")
    else:
        # 普通用户只能查询自己的任务
        task_info = TaskModel.query.filter_by(upload_id=upload_id, user_id=user_id).first()

    if not task_info:
        logger.warning(f"Source code request failed: Task not found for upload {upload_id} and user {user_id}")
        return HttpResponse.not_found("记录不存在")

    file_path = os.path.join(os.path.dirname(task_info.task_dir), f"{task_info.algorithm}.cc")
    if not os.path.exists(file_path):
        logger.warning(f"Source code file not found: {file_path}")
        return HttpResponse.not_found("源代码文件不存在，可能已被删除")

    logger.info(f"Sending source code file: {file_path}")
    return HttpResponse.send_attachment_file(file_path)
