import logging
import platform

import psutil
from flask import Blueprint
from flask_jwt_extended import jwt_required, current_user

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
    target_user.restore()

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
        task_dict = task.to_detail_dict()
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
                'deleted_users': deleted_users
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
    return HttpResponse.ok(
        data={
            'system': {
                'platform': platform.platform(),
                'python_version': platform.python_version(),
                'cpu_percent': psutil.cpu_percent(),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_usage': psutil.disk_usage('/').percent
            },
            'config': {
                'courses': config.Course.CNAME_LIST,
                'log_level': config.Logging.LOG_LEVEL,
                'debug': get_app().debug,
            }
        }
    )
