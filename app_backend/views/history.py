import logging

from flask import Blueprint
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt, current_user

from app_backend.model.task_model import TaskModel, to_history_dict
from app_backend.validators.decorators import validate_request, get_validated_data
from app_backend.validators.schemas import HistoryDetailSchema
from app_backend.vo.http_response import HttpResponse

history_bp = Blueprint('history', __name__)
logger = logging.getLogger(__name__)


@history_bp.route("/history_get_history_records", methods=["GET"])
@jwt_required()
def return_history_records():
    user_id = get_jwt_identity()
    cname = get_jwt().get('cname')
    logger.debug(f"History records request for user {user_id} in competition {cname}")

    history_records = TaskModel.query.filter_by(user_id=user_id, cname=cname).all()
    records = to_history_dict(history_records)
    logger.info(f"Found {len(records)} history records for user {user_id}")
    return HttpResponse.ok(history=records)


@history_bp.route("/history_get_history_record_detail", methods=["POST"])
@jwt_required()
@validate_request(HistoryDetailSchema)
def get_record_detail():
    data = get_validated_data(HistoryDetailSchema)
    upload_id = data.upload_id
    cname = get_jwt().get('cname')
    logger.debug(f"History record detail request for upload {upload_id} in competition {cname}")
    # 判断是否为管理员，如果是管理员，则可以查询所有记录
    if current_user.is_admin():
        record = TaskModel.query.filter_by(upload_id=upload_id).all()
        logger.debug(f"Admin {current_user.username} requesting detailed record for upload {upload_id}")
    else:
        record = TaskModel.query.filter_by(upload_id=upload_id, cname=cname).all()

    if not record:
        logger.warning(f"No records found for upload {upload_id} in competition {cname}")
        return HttpResponse.not_found("记录不存在")
    records = [r.to_detail_dict(current_user.is_admin()) for r in record]  # 返回的是所有记录，需要前端聚合
    logger.info(f"Found {len(records)} detailed records for upload {upload_id}")
    return HttpResponse.ok(tasks=records)
