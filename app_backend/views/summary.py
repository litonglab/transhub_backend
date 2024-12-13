from flask import Blueprint, request

from app_backend.model.Rank_model import Rank_model
from app_backend.security.safe_check import check_user_state
from app_backend.vo.response import myResponse

summary_bp = Blueprint('summary', __name__)
@summary_bp.route("/summary_get_ranks", methods=["POST"])
def return_ranks():
    user_id = request.json.get('user_id')
    cname = request.json.get('cname')
    if not check_user_state(user_id):
        return myResponse(200, "Please login firstly!")
    ranks = Rank_model.query.filter_by(cname=cname).all()
    res = []
    # 按照task_score排序, 降序
    ranks = sorted(ranks, key=lambda x: x.task_score, reverse=True)
    for rank in ranks:
        res.append(rank.to_dict())
    return myResponse(200, "Success", rank=res)


