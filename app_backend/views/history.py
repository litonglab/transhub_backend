from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from app_backend.decorators.validators import validate_request
# from app_backend.model.User_model import User_model
from app_backend.model.Task_model import Task_model, to_history_dict
from app_backend.validators.schemas import HistoryDetailSchema
from app_backend.vo import HttpResponse

history_bp = Blueprint('history', __name__)


@history_bp.route("/history_get_history_records", methods=["GET"])
@jwt_required()
def return_history_records():
    user_id = get_jwt_identity()
    cname = get_jwt().get('cname')
    history_records = Task_model.query.filter_by(user_id=user_id, cname=cname).all()
    records = to_history_dict(history_records)
    return HttpResponse.ok(history=records)


@history_bp.route("/history_get_history_record_detail", methods=["POST"])
@jwt_required()
@validate_request(HistoryDetailSchema)
def get_record_detail():
    data = request.validated_data
    upload_id = data.upload_id
    cname = get_jwt().get('cname')
    # if not check_upload_auth(upload_id,user_id):
    #     return myResponse(400, "User is not authorized to access this task.")
    record = Task_model.query.filter_by(upload_id=upload_id, cname=cname).all()
    if not record:
        return HttpResponse.fail("No such record.")
    records = [r.to_detail_dict() for r in record]  # 返回的是所有记录，需要前端聚合

    return HttpResponse.ok(tasks=records)
