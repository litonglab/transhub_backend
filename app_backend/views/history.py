from flask import Blueprint, request

# from app_backend.model.User_model import User_model
from app_backend.model.Task_model import Task_model,to_history_dict
from app_backend.security.safe_check import check_user_state
from app_backend.vo.response import myResponse

history_bp = Blueprint('history', __name__)


@history_bp.route("/history_get_history_records", methods=["POST"])
def return_history_records():
    user_id = request.json.get('user_id')
    cname = request.json.get('cname')
    if not check_user_state(user_id):
        return myResponse(400, "Please login firstly.")
    history_records = Task_model.query.filter_by(user_id=user_id,cname=cname).all()
    records = to_history_dict(history_records)
    return myResponse(200, "Success", history=records)

@history_bp.route("/history_get_history_record_detail",methods=["POST"])
def get_record_detail():
    #参数是user_id和upload_id
    data = request.get_json()
    user_id = data.get('user_id')
    upload_id = data.get('upload_id')
    cname = data.get('cname')
    if not check_user_state(user_id):
        return myResponse(400, "Please login firstly.")
    # if not check_upload_auth(upload_id,user_id):
    #     return myResponse(400, "User is not authorized to access this task.")
    record = Task_model.query.filter_by(upload_id=upload_id,cname=cname).all()
    if not record:
        return myResponse(400, "No such record.")
    records = [r.to_detail_dict() for r in record]  # 返回的是所有记录，需要前端聚合

    return myResponse(200, "Success", tasks=records)



