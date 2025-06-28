import logging
import os
import platform
import time
from datetime import date, datetime

import psutil
from flask import Blueprint, Response, stream_with_context
from flask_jwt_extended import jwt_required, current_user

from app_backend import db
from app_backend import get_default_config, get_app
from app_backend.model.competition_model import CompetitionModel
from app_backend.model.task_model import TaskModel
from app_backend.model.user_model import UserModel, UserRole
from app_backend.security.admin_decorators import admin_required
from app_backend.validators.decorators import validate_request, get_validated_data
from app_backend.validators.schemas import (
    AdminUserListSchema, AdminUserUpdateSchema,
    AdminTaskListSchema, AdminPasswordResetSchema,
    AdminUserDeleteSchema, AdminUserRestoreSchema
)
from app_backend.vo.http_response import HttpResponse

admin_bp = Blueprint('admin', __name__)
logger = logging.getLogger(__name__)
config = get_default_config()


@admin_bp.route('/admin/users', methods=['GET'])
@jwt_required()
@admin_required()
@validate_request(AdminUserListSchema)
def get_users():
    """获取用户列表"""
    data = get_validated_data(AdminUserListSchema)

    query = UserModel.query

    # 删除状态筛选
    if data.deleted is not None:
        query = query.filter(UserModel.is_deleted == data.deleted)
    else:
        # 默认只显示所有用户
        query = query.filter()

    # 搜索筛选
    if data.keyword:
        query = query.filter(
            (UserModel.username.contains(data.keyword)) |
            (UserModel.real_name.contains(data.keyword)) |
            (UserModel.sno.contains(data.keyword))
        )

    # 角色筛选
    if data.role:
        query = query.filter(UserModel.role == data.role)

    # 活跃状态筛选
    if data.active is not None:
        if data.active:
            # 活跃用户：未删除且未锁定
            query = query.filter(UserModel.is_deleted == False, UserModel.is_locked == False)
        else:
            # 非活跃用户：已删除或已锁定
            query = query.filter((UserModel.is_deleted == True) | (UserModel.is_locked == True))

    # 分页
    total = query.count()
    users = query.offset((data.page - 1) * data.size).limit(data.size).all()

    logger.info(
        f"Admin {current_user.username} fetched user list, total: {total}, page: {data.page}, size: {data.size}")

    return HttpResponse.ok(
        data={
            'users': [user.to_dict() for user in users],
            'pagination': {
                'page': data.page,
                'size': data.size,
                'total': total,
                'pages': (total + data.size - 1) // data.size
            }
        }
    )


@admin_bp.route('/admin/users/update', methods=['POST'])
@jwt_required()
@admin_required()
@validate_request(AdminUserUpdateSchema)
def update_user():
    """更新用户信息"""
    data = get_validated_data(AdminUserUpdateSchema)
    # 使用current_user，无需手动查询当前用户
    current_user_obj = current_user

    target_user = UserModel.query.get(data.user_id)
    if not target_user:
        logger.warning(f"User update failed: User with ID {data.user_id} does not exist")
        return HttpResponse.not_found("用户不存在")

    # 权限检查：只有超级管理员可以修改其他管理员
    if target_user.is_admin() and not current_user_obj.is_super_admin():
        logger.warning(
            f"User update failed: User {current_user_obj.username} tried to modify admin user {target_user.username}")
        return HttpResponse.forbidden("只有超级管理员可以修改管理员用户")

    # 防止自己锁定自己
    if data.is_locked and target_user.user_id == current_user_obj.user_id:
        logger.warning(f"User update failed: User {current_user_obj.username} tried to lock their own account")
        return HttpResponse.fail("不能锁定自己的账户")

    # 角色更改权限检查：只有超级管理员才能更改其他用户的角色
    if data.role is not None and not current_user_obj.is_super_admin():
        logger.warning(
            f"User update failed: User {current_user_obj.username} tried to change role of user {target_user.username}")
        return HttpResponse.forbidden("只有超级管理员可以更改用户角色")

    # 更新字段
    if data.role is not None:
        target_user.role = data.role
    if data.is_locked is not None:
        target_user.is_locked = data.is_locked

    target_user.save()
    logger.info(f"Admin {current_user_obj.username} updated user {target_user.username}")

    return HttpResponse.ok()


@admin_bp.route('/admin/users/reset_password', methods=['POST'])
@jwt_required()
@admin_required()
@validate_request(AdminPasswordResetSchema)
def reset_user_password():
    """重置用户密码"""
    data = get_validated_data(AdminPasswordResetSchema)
    # 使用current_user，无需手动查询当前用户
    current_user_obj = current_user

    target_user = UserModel.query.get(data.user_id)
    if not target_user:
        logger.warning(f"User reset password failed: User with ID {data.user_id} does not exist")
        return HttpResponse.not_found("用户不存在")

    # 权限检查：只有超级管理员可以重置其他管理员的密码
    if target_user.is_admin() and not current_user_obj.is_super_admin():
        logger.warning(
            f"User reset password failed: User {current_user_obj.username} tried to reset password for admin user {target_user.username}")
        return HttpResponse.forbidden("只有超级管理员可以重置管理员用户的密码")

    # 防止重置自己的密码（建议管理员使用正常修改密码功能）
    if target_user.user_id == current_user_obj.user_id:
        logger.warning(
            f"User reset password failed: User {current_user_obj.username} tried to reset their own password")
        return HttpResponse.fail("不能重置自己的密码，请使用修改密码功能")

    # 重置密码
    target_user.reset_password(data.new_password)

    logger.info(f"Admin {current_user_obj.username} reset password for user {target_user.username}")

    return HttpResponse.ok(f"用户 {target_user.username} 的密码已重置为 {data.new_password}")


@admin_bp.route('/admin/users/delete', methods=['POST'])
@jwt_required()
@admin_required()
@validate_request(AdminUserDeleteSchema)
def delete_user():
    """软删除用户"""
    data = get_validated_data(AdminUserDeleteSchema)
    # 使用current_user，无需手动查询当前用户
    current_user_obj = current_user

    target_user = UserModel.query.get(data.user_id)
    if not target_user:
        logger.warning(f"User delete failed: User with ID {data.user_id} does not exist")
        return HttpResponse.not_found("用户不存在")

    # 检查用户是否已经被删除
    if target_user.is_deleted:
        logger.warning(f"User delete failed: User {target_user.username} is already deleted")
        return HttpResponse.fail("用户已经被删除")

    # 权限检查：只有超级管理员可以删除其他管理员
    if target_user.is_admin() and not current_user_obj.is_super_admin():
        logger.warning(
            f"User delete failed: User {current_user_obj.username} tried to delete admin user {target_user.username}")
        return HttpResponse.forbidden("只有超级管理员可以删除管理员用户")

    # 防止删除自己
    if target_user.user_id == current_user_obj.user_id:
        logger.warning(f"User delete failed: User {current_user_obj.username} tried to delete their own account")
        return HttpResponse.fail("不能删除自己的账户")

    # 软删除用户
    target_user.soft_delete()

    logger.info(f"Admin {current_user_obj.username} deleted user {target_user.username}")

    return HttpResponse.ok(f"用户 {target_user.username} 已被删除")


@admin_bp.route('/admin/users/restore', methods=['POST'])
@jwt_required()
@admin_required()
@validate_request(AdminUserRestoreSchema)
def restore_user():
    """恢复被删除的用户"""
    data = get_validated_data(AdminUserRestoreSchema)
    # 使用current_user，无需手动查询当前用户
    current_user_obj = current_user

    target_user = UserModel.query.get(data.user_id)
    if not target_user:
        logger.warning(f"User restore failed: User with ID {data.user_id} does not exist")
        return HttpResponse.not_found("用户不存在")

    # 检查用户是否已经被删除
    if not target_user.is_deleted:
        logger.warning(f"User restore failed: User {target_user.username} is not deleted")
        return HttpResponse.fail("用户未被删除，无需恢复")

    # 权限检查：只有超级管理员可以恢复管理员用户
    if target_user.is_admin() and not current_user_obj.is_super_admin():
        logger.warning(
            f"User restore failed: User {current_user_obj.username} tried to restore admin user {target_user.username}")
        return HttpResponse.forbidden("只有超级管理员可以恢复管理员用户")

    # 恢复用户
    try:
        target_user.restore()
    except ValueError as e:
        logger.warning(f"User restore failed: {str(e)}")
        return HttpResponse.fail(str(e))
    except Exception as e:
        logger.error(f"User restore failed: {str(e)}", exc_info=True)
        return HttpResponse.internal_error("恢复用户时发生错误")

    logger.info(f"Admin {current_user_obj.username} restored user {target_user.username}")

    return HttpResponse.ok(f"用户 {target_user.username} 已被恢复")


@admin_bp.route('/admin/tasks', methods=['GET'])
@jwt_required()
@admin_required()
@validate_request(AdminTaskListSchema)
def get_tasks():
    """获取任务列表"""
    data = get_validated_data(AdminTaskListSchema)

    query = TaskModel.query

    # 用户筛选
    if data.user_id:
        query = query.filter(TaskModel.user_id == data.user_id)

    # 状态筛选
    if data.status:
        query = query.filter(TaskModel.task_status == data.status)

    # 比赛筛选
    if data.cname:
        query = query.filter(TaskModel.cname == data.cname)

    # 按创建时间降序排列
    query = query.order_by(TaskModel.created_time.desc())

    # 分页
    total = query.count()
    tasks = query.offset((data.page - 1) * data.size).limit(data.size).all()

    # 获取用户信息
    task_list = []
    for task in tasks:
        user = UserModel.query.get(task.user_id)
        task_dict = task.to_detail_dict(current_user)  # 传递当前用户（管理员）
        task_dict['username'] = user.username if user else 'Unknown'
        task_list.append(task_dict)

    logger.info(
        f"Admin {current_user.username} fetched task list, total: {total}, page: {data.page}, size: {data.size}")

    return HttpResponse.ok(
        data={
            'tasks': task_list,
            'pagination': {
                'page': data.page,
                'size': data.size,
                'total': total,
                'pages': (total + data.size - 1) // data.size
            }
        }
    )


@admin_bp.route('/admin/stats', methods=['GET'])
@jwt_required()
@admin_required()
def get_stats():
    """获取系统统计信息"""

    # 基础统计
    total_users = UserModel.query.filter_by(is_deleted=False).count()
    total_tasks = TaskModel.query.count()
    active_users = UserModel.query.filter(UserModel.is_deleted == False, UserModel.is_locked == False).count()
    deleted_users = UserModel.query.filter_by(is_deleted=True).count()

    # 计算今日提交数（通过统计今天创建的不同upload_id数量）
    today_submit = TaskModel.query.filter(
        db.func.date(TaskModel.created_time) == date.today()
    ).with_entities(TaskModel.upload_id).distinct().count()

    # 任务状态统计
    task_stats = {}
    try:
        from app_backend.model.task_model import TaskStatus
        for status in TaskStatus:
            count = TaskModel.query.filter(TaskModel.task_status == status.value).count()
            task_stats[status.value] = count
    except Exception as e:
        logger.warning(f"Could not get TaskStatus enum: {e}")
        # 如果没有TaskStatus枚举，使用简单的状态统计
        task_stats = {"total": total_tasks}

    # 比赛参与统计
    competition_stats = {}
    for cname in config.Course.CNAME_LIST:
        participant_count = CompetitionModel.query.filter(CompetitionModel.cname == cname).count()
        competition_stats[cname] = participant_count

    # 角色统计（仅统计未删除用户）
    role_stats = {}
    for role in UserRole:
        count = UserModel.query.filter(UserModel.role == role.value, UserModel.is_deleted == False).count()
        role_stats[role.value] = count

    return HttpResponse.ok(
        data={
            'overview': {
                'total_users': total_users,
                'active_users': active_users,
                'total_tasks': total_tasks,
                'deleted_users': deleted_users,
                'today_submit': today_submit
            },
            'task_stats': task_stats,
            'competition_stats': competition_stats,
            'role_stats': role_stats
        }
    )


@admin_bp.route('/admin/system/info', methods=['GET'])
@jwt_required()
# @role_required(UserRole.SUPER_ADMIN) #（仅超级管理员）
@admin_required()
def get_system_info():
    """获取系统信息"""

    # 获取当前进程信息
    current_process = psutil.Process(os.getpid())
    process_start_time = datetime.fromtimestamp(current_process.create_time())
    process_uptime = datetime.now() - process_start_time

    # 尝试获取相关进程信息
    related_processes = []
    try:
        for proc in psutil.process_iter(['pid', 'name', 'create_time', 'cmdline']):
            try:
                if proc.info['cmdline'] and any(
                        'gunicorn' in cmd or 'dramatiq' in cmd or 'run.py' in cmd for cmd in proc.info['cmdline']):
                    start_time = datetime.fromtimestamp(proc.info['create_time'])
                    uptime = datetime.now() - start_time
                    related_processes.append({
                        'pid': proc.info['pid'],
                        'name': proc.info['name'],
                        'start_time': start_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'uptime_seconds': int(uptime.total_seconds()),
                        'uptime_formatted': str(uptime).split('.')[0],  # 去掉微秒
                        'cmdline': ' '.join(proc.info['cmdline'][:3])  # 只显示前3个命令参数
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                logger.error(
                    f"Error accessing process {proc.info['pid']} ({proc.info['name']}): {e}", exc_info=True)
                continue
    except Exception as e:
        logger.error(f"Error getting process info: {e}", exc_info=True)

    return HttpResponse.ok(
        data={
            'system': {
                'platform': platform.platform(),
                'python_version': platform.python_version(),
                'cpu_percent': psutil.cpu_percent(),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_usage': psutil.disk_usage('/').percent
            },
            'process': {
                'current_pid': os.getpid(),
                'start_time': process_start_time.strftime('%Y-%m-%d %H:%M:%S'),
                'uptime_seconds': int(process_uptime.total_seconds()),
                'uptime_formatted': str(process_uptime).split('.')[0],  # 去掉微秒显示
                'related_processes': related_processes
            },
            'config': {
                'courses': config.Course.CNAME_LIST,
                'course_detail': config.Course.ALL_CLASS,
                'log_level': config.Logging.LOG_LEVEL,
                'debug': get_app().debug,
            }
        }
    )


@admin_bp.route('/admin/system/logs', methods=['GET'])
@jwt_required()
@admin_required()
def get_log_files():
    """获取日志文件列表"""
    log_dir = config.Logging.LOG_DIR
    if not os.path.exists(log_dir):
        return HttpResponse.fail("日志目录不存在")
    log_files = []
    for filename in os.listdir(log_dir):
        if filename.endswith('.log'):
            file_path = os.path.join(log_dir, filename)
            stat = os.stat(file_path)
            log_files.append({
                'name': filename,
                'size': stat.st_size,
                'modified_time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stat.st_mtime))
            })
    log_files.sort(key=lambda x: x['modified_time'], reverse=True)
    return HttpResponse.ok(data={'log_files': log_files, 'log_dir': log_dir})


@admin_bp.route('/admin/system/logs/stream/<log_name>', methods=['GET'])
@jwt_required()
@admin_required()
def stream_log_file(log_name):
    """流式获取日志内容（Server-Sent Events）"""
    log_dir = config.Logging.LOG_DIR
    log_path = os.path.join(log_dir, log_name)
    if not os.path.exists(log_path) or not log_name.endswith('.log'):
        return HttpResponse.not_found("日志文件不存在")
    # 防止目录遍历
    if not os.path.commonpath([log_dir, log_path]) == log_dir:
        return HttpResponse.forbidden("不允许访问此文件")

    def generate():
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            total_lines = len(lines)
            start_line = max(0, total_lines - 5000)  # 从倒数5000行开始，如果文件不足则从开头开始

            # 先发送历史日志
            for line in lines[start_line:]:
                yield f"data: {line.rstrip()}\n\n"

            # 实时监控新增内容
            f.seek(0, os.SEEK_END)  # 移动到文件末尾
            while True:
                line = f.readline()
                if line:
                    yield f"data: {line.rstrip()}\n\n"
                else:
                    time.sleep(1)  # 每1秒检查一次新内容

    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no"
    }
    return Response(stream_with_context(generate()), headers=headers)
