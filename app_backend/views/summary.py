import logging

from flask import Blueprint
from flask_jwt_extended import jwt_required, get_jwt

from app_backend import cache
from app_backend.model.rank_model import RankModel
from app_backend.vo import HttpResponse

summary_bp = Blueprint('summary', __name__)
logger = logging.getLogger(__name__)


@cache.memoize(timeout=10)
def get_ranks_for_competition(cname):
    """获取比赛榜单的缓存函数"""
    ranks = RankModel.query.filter_by(cname=cname).all()
    # 按照task_score排序, 降序
    ranks = sorted(ranks, key=lambda x: x.task_score, reverse=True)
    logger.debug(f"query {len(ranks)} ranks for competition {cname}")
    return [rank.to_dict() for rank in ranks]


@summary_bp.route("/summary_get_ranks", methods=["GET"])
@jwt_required()
def return_ranks():
    cname = get_jwt().get('cname')
    logger.debug(f"Rank request for competition {cname}")

    ranks = get_ranks_for_competition(cname)
    logger.debug(f"Returning {len(ranks)} ranks for competition {cname}")
    return HttpResponse.ok(rank=ranks)
