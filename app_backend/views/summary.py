import logging

from flask import Blueprint
from flask_jwt_extended import jwt_required, get_jwt, current_user

from app_backend import cache, get_default_config, redis_client
from app_backend.model.rank_model import RankModel
from app_backend.model.user_model import UserModel
from app_backend.utils.utils import get_record_by_permission
from app_backend.validators.decorators import validate_request, get_validated_data
from app_backend.validators.schemas import DeleteRankSchema
from app_backend.vo.http_response import HttpResponse

summary_bp = Blueprint('summary', __name__)
logger = logging.getLogger(__name__)
config = get_default_config()


@cache.memoize(timeout=10 * 60)
def get_ranks_for_competition(cname, is_admin=False):
    """获取比赛榜单的缓存函数，缓存10分钟"""
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
            rank_dict['to_admin'] = {'sno': sno,
                                     'rank_id': rank.rank_id, }
        result.append(rank_dict)
    return result


def reset_rank_cache(cname):
    """重置比赛榜单缓存"""
    cache.delete_memoized(get_ranks_for_competition, cname, True)
    cache.delete_memoized(get_ranks_for_competition, cname, False)
    logger.debug(f"Cache for competition {cname} has been reset.")


@summary_bp.route("/summary_delete_rank", methods=["DELETE"])
@jwt_required()
@validate_request(DeleteRankSchema)
def delete_rank():
    data = get_validated_data(DeleteRankSchema)
    cname = get_jwt().get('cname')
    user = current_user
    rank = get_record_by_permission(RankModel,
                                    {'rank_id': data.rank_id, 'cname': cname},
                                    {'cname': cname})
    if not rank:
        logger.warning(
            f"Rank deletion failed: Rank with ID {data.rank_id} not found for competition {cname} by user {user.username}")
        return HttpResponse.not_found("榜单记录不存在或无权限")

    competition_remaining_time = config.get_competition_remaining_time(cname)
    if config.is_competition_ended(cname) or competition_remaining_time <= 12 * 60 * 60:
        logger.warning(
            f"Rank deletion failed: Competition {cname} has ended, or remaining time(competition_remaining_time) is less than 12 hours, "
            f"cannot delete rank by user {user.username}")
        return HttpResponse.fail("比赛截止前12小时内及截止后，无法删除榜单记录")

    # 检查非管理用户的12小时调用限制
    if not user.is_admin():
        cache_key = f"rank_delete_limit:{cname}:{user.user_id}"
        result = redis_client.set(cache_key, "0", nx=True, ex=12 * 60 * 60)
        if not result:
            remaining_seconds = redis_client.ttl(cache_key)
            remaining_hours = remaining_seconds / 3600
            logger.warning(
                f"Rank deletion failed: User {user.username} tried to delete rank too soon, {remaining_hours:.1f} hours remaining")
            return HttpResponse.fail(f"每12小时只能删除一次榜单记录，还需等待 {remaining_hours:.1f} 小时")

    try:
        rank.delete()
        # 清除榜单缓存
        reset_rank_cache(cname)
        logger.warning(
            f"Rank with ID {data.rank_id}, cname {cname}, username {rank.username} deleted by user {user.username}")
        return HttpResponse.ok()

    except Exception as e:
        logger.error(f"Error deleting rank with ID {data.rank_id} by user {user.username}: {str(e)}", exc_info=True)
        return HttpResponse.fail("删除榜单记录失败")


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
