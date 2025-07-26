import logging
import os

from flask import Blueprint
from flask_jwt_extended import jwt_required, current_user

from app_backend.model.task_model import TaskModel
from app_backend.utils.utils import get_record_by_permission
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
    user = current_user
    logger.debug(f"Source code request for upload {upload_id} by user {user.username}")

    # 使用通用工具函数
    task_info = get_record_by_permission(TaskModel, {'upload_id': upload_id})

    if not task_info:
        logger.warning(f"Source code request failed: Task not found for upload {upload_id} and user {user.username}")
        return HttpResponse.not_found("记录不存在或无权限")

    file_path = os.path.join(task_info.task_dir, f"{task_info.algorithm}.cc")
    if not os.path.exists(file_path):
        logger.warning(f"Source code file not found: {file_path}")
        return HttpResponse.not_found("源代码文件不存在，可能已被删除")

    logger.info(f"Sending source code file: {file_path}")
    return HttpResponse.send_attachment_file(file_path)
