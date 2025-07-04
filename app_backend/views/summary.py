import logging

from flask import Blueprint
from flask_jwt_extended import jwt_required, get_jwt, current_user

from app_backend import cache
from app_backend.model.rank_model import RankModel
from app_backend.model.user_model import UserModel
from app_backend.vo.http_response import HttpResponse

summary_bp = Blueprint('summary', __name__)
logger = logging.getLogger(__name__)


@cache.memoize(timeout=10)
def get_ranks_for_competition(cname, is_admin=False):
    """获取比赛榜单的缓存函数"""
    # 使用JOIN查询一次性获取榜单和用户信息
    ranks_with_users = (RankModel.query
                        .join(UserModel, RankModel.user_id == UserModel.user_id)
                        .filter(RankModel.cname == cname)
                        .with_entities(RankModel, UserModel.sno, UserModel.real_name)
                        .all())

    logger.debug(f"query {len(ranks_with_users)} ranks with user info for competition {cname}")

    result = []
    for rank, sno, real_name in ranks_with_users:
        rank_dict = rank.to_dict()
        rank_dict['real_name'] = real_name
        if is_admin:
            rank_dict['to_admin'] = {'sno': sno, }
        result.append(rank_dict)
    return result


@summary_bp.route("/summary_get_ranks", methods=["GET"])
@jwt_required()
def return_ranks():
    cname = get_jwt().get('cname')
    logger.debug(f"Rank request for competition {cname}")

    # 判断当前用户是否为admin
    is_admin = current_user.is_admin()
    ranks = get_ranks_for_competition(cname, is_admin)
    logger.debug(f"Returning {len(ranks)} ranks for competition {cname}, user is admin: {is_admin}")
    return HttpResponse.ok(rank=ranks)
