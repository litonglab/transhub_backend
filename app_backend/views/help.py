import logging
import os

import psutil
from flask import Blueprint
from flask_jwt_extended import jwt_required, get_jwt

from app_backend import cache
from app_backend import get_default_config
from app_backend.model.task_model import TaskStatus
from app_backend.views.admin import _get_course_specific_stats
from app_backend.vo.http_response import HttpResponse

help_bp = Blueprint('help', __name__)
logger = logging.getLogger(__name__)
config = get_default_config()


# @help_bp.route("/help_get_cca_guide", methods=["POST"])
# def return_cca_file():
#     cname = request.json['cname']
#     if cname == cctraining_config.cname:
#         return send_file(cctraining_config.cca_guide_path, as_attachment=True)
#     else:
#         return myResponse(400, "No cca guide found.")
#
#
# @help_bp.route("/get_user_guide", methods=["POST"])
# def return_guide_file():
#     cname = request.json['cname']
#     if cname == cctraining_config.cname:
#         return send_file(cctraining_config.user_guide_path, as_attachment=True)
#     else:
#         return myResponse(400, "No user guide found.")


@help_bp.route("/help_get_tutorial", methods=["GET"])
@jwt_required()
def get_tutorial():
    cname = get_jwt().get('cname')
    logger.debug(f"Tutorial request for competition {cname}")

    _config = config.get_course_config(cname)
    if _config and os.path.exists(_config['zhinan_path']):
        logger.info(f"Sending tutorial file: {_config['zhinan_path']}")
        return HttpResponse.send_attachment_file(_config['zhinan_path'])
    else:
        logger.error(f"Tutorial not found for competition {cname}")
        return HttpResponse.not_found("文档不存在")


# 此url参数手动校验，不使用 @validate_request(Schema)
@help_bp.route("/help_get_tutorial_images/images/<image_file_name>", methods=["GET"])
@jwt_required()
def get_tutorial_image(image_file_name):
    cname = get_jwt().get('cname')
    logger.debug(f"Tutorial image request for competition {cname}, image: {image_file_name}")
    _config = config.get_course_config(cname)

    if not _config:
        logger.error(f"Configuration not found for competition {cname}")
        return HttpResponse.not_found("配置不存在")

    # 获取文件后缀并校验
    allowed_image_exts = ('.png', '.jpg', '.jpeg', '.svg', '.bmp', '.webp')
    _, ext = os.path.splitext(image_file_name)
    if ext.lower() not in allowed_image_exts:
        logger.error(f"Illegal image file extension: {image_file_name}")
        return HttpResponse.fail("不支持的文件类型")

    image_dir = _config['image_path']
    image_path = os.path.join(image_dir, image_file_name)

    real_image_path = os.path.realpath(image_path)
    real_image_dir = os.path.realpath(image_dir)
    if not real_image_path.startswith(real_image_dir):
        logger.error(f"Directory traversal attempt: {image_file_name}")
        return HttpResponse.fail("非法访问")

    if os.path.exists(image_path) and os.path.isfile(image_path):
        logger.debug(f"Sending tutorial image file: {image_path}")
        return HttpResponse.send_attachment_file(image_path)
    else:
        logger.error(f"Tutorial image not found: {image_path}")
        return HttpResponse.not_found()


@help_bp.route('/help_get_pantheon', methods=["GET"])
def get_pantheon():
    return HttpResponse.ok(pantheon=config.Course.CNAME_LIST)


@help_bp.route("/help_get_competition_info", methods=["GET"])
@jwt_required()
def get_competition_info():
    """ Returns the start and end time of the competition for the current user.
    """
    cname = get_jwt().get('cname')
    logger.debug(f"Competition time request for {cname}")

    _config = config.get_course_config(cname)
    time_stmp = config.get_competition_timestamp(cname)
    data = {
        "time_stmp": time_stmp,
        "max_active_uploads_per_user": _config['max_active_uploads_per_user'],
    }
    logger.debug(
        f"Competition info for {cname}: start={_config['start_time']}, end={_config['end_time']}, max_active_uploads_per_user={_config['max_active_uploads_per_user']}")
    return HttpResponse.ok(data=data)


@cache.memoize(timeout=5)
def _get_system_status():
    """获取系统状态"""
    cpu_percent = psutil.cpu_percent()
    mem_percent = psutil.virtual_memory().percent

    if cpu_percent > 95 or mem_percent > 90:
        return 2  # 满载
    elif cpu_percent > 85 or mem_percent > 80:
        return 1  # 重载
    else:
        return 0  # 轻载


@cache.memoize(timeout=30)
def _get_queue_status(cname):
    """获取任务队列状态"""
    # 任务队列统计：直接用admin的缓存接口统计所有课程的任务数
    course_specific_stats = _get_course_specific_stats(cname)
    all_stats = course_specific_stats['current_course_task_stats']
    total_tasks = 0
    for status in [TaskStatus.QUEUED.value, TaskStatus.COMPILING.value, TaskStatus.RUNNING.value]:
        total_tasks += all_stats.get(status, 0)

    # 匹配区间
    if total_tasks < 10:
        return 0
    elif total_tasks < 50:
        return 1
    elif total_tasks < 100:
        return 2
    elif total_tasks < 200:
        return 3
    elif total_tasks < 500:
        return 4
    elif total_tasks < 1000:
        return 5
    elif total_tasks < 2000:
        return 6
    else:
        return 7


@help_bp.route("/help_get_system_info", methods=["GET"])
@jwt_required()
def get_system_info():
    cname = get_jwt().get('cname')

    data = {
        "system_status": _get_system_status(),  # 0: 轻载, 1: 重载, 2: 满载
        "queue_status": _get_queue_status(cname),  # 0-7
    }
    return HttpResponse.ok(data=data)
