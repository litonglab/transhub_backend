import logging
import os
import platform
import time
from datetime import date, datetime, timedelta

import psutil
from flask import Blueprint, Response, stream_with_context, current_app
from flask_jwt_extended import jwt_required, current_user, get_jwt

from app_backend import cache
from app_backend import db
from app_backend import get_default_config
from app_backend.model.competition_model import CompetitionModel
from app_backend.model.task_model import TaskModel
from app_backend.model.task_model import TaskStatus
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


def _validate_log_file(log_name):
    """
    验证日志文件的合法性和安全性

    Args:
        log_name (str): 日志文件名

    Returns:
        tuple: (is_valid, log_path, error_response)
               - is_valid: 文件是否有效
               - log_path: 完整的文件路径（仅在有效时返回）
               - error_response: 错误响应（仅在无效时返回）
    """
    log_dir = config.Logging.LOG_DIR
    log_path = os.path.join(log_dir, log_name)

    # 检查文件是否存在且为日志文件
    if not os.path.exists(log_path) or not log_name.endswith('.log'):
        logger.error(f"Log file {log_name} does not exist or is not a valid log file")
        return False, None, HttpResponse.not_found("日志文件不存在")

    # 防止目录遍历攻击
    if not os.path.commonpath([log_dir, log_path]) == log_dir:
        logger.error(f"Log file {log_name} is outside the allowed log directory")
        return False, None, HttpResponse.forbidden("不允许访问此文件")

    return True, log_path, None


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

    # 课程报名筛选
    if hasattr(data, 'cname') and data.cname:
        # 通过JOIN查询筛选报名了指定课程的用户
        query = query.join(CompetitionModel, UserModel.user_id == CompetitionModel.user_id) \
            .filter(CompetitionModel.cname == data.cname)

    # 活跃状态筛选
    if data.active is not None:
        if data.active:
            # 活跃用户：未删除且未锁定
            query = query.filter(UserModel.is_deleted == False, UserModel.is_locked == False)
        else:
            # 非活跃用户：已删除或已锁定
            query = query.filter((UserModel.is_deleted == True) | (UserModel.is_locked == True))

    # 分页计算
    total = query.count()

    # 使用JOIN查询直接获取用户及其课程信息，避免多次查询
    # 首先获取分页后的用户ID列表
    user_ids_query = query.with_entities(UserModel.user_id) \
        .offset((data.page - 1) * data.size) \
        .limit(data.size)
    user_ids = [uid[0] for uid in user_ids_query.all()]

    if user_ids:
        # 使用LEFT JOIN一次性获取用户信息和课程信息
        users_with_courses = db.session.query(
            UserModel,
            CompetitionModel.cname
        ).outerjoin(
            CompetitionModel, UserModel.user_id == CompetitionModel.user_id
        ).filter(
            UserModel.user_id.in_(user_ids)
        ).all()

        # 构建用户字典和课程映射
        users_dict = {}
        user_courses_map = {}

        for user, course_name in users_with_courses:
            # 构建用户字典（避免重复）
            if user.user_id not in users_dict:
                users_dict[user.user_id] = user
                user_courses_map[user.user_id] = []

            # 添加课程信息
            if course_name and course_name not in user_courses_map[user.user_id]:
                user_courses_map[user.user_id].append(course_name)

        # 按原始顺序构建用户列表
        user_list = []
        for user_id in user_ids:
            if user_id in users_dict:
                user = users_dict[user_id]
                user_dict = user.to_dict()
                user_dict['enrolled_courses'] = user_courses_map.get(user_id, [])
                user_list.append(user_dict)
    else:
        user_list = []

    logger.info(
        f"Admin {current_user.username} fetched user list, total: {total}, page: {data.page}, size: {data.size}")

    return HttpResponse.ok(
        data={
            'users': user_list,
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

    target_user = UserModel.query.get(data.user_id)
    if not target_user:
        logger.warning(f"User update failed: User with ID {data.user_id} does not exist")
        return HttpResponse.not_found("用户不存在")

    # 权限检查：只有超级管理员可以修改其他管理员
    if target_user.is_admin() and not current_user.is_super_admin():
        logger.warning(
            f"User update failed: User {current_user.username} tried to modify admin user {target_user.username}")
        return HttpResponse.forbidden("只有超级管理员可以修改管理员用户")

    # 防止自己锁定自己
    if data.is_locked and target_user.user_id == current_user.user_id:
        logger.warning(f"User update failed: User {current_user.username} tried to lock their own account")
        return HttpResponse.fail("不能锁定自己的账户")

    # 角色更改权限检查：只有超级管理员才能更改其他用户的角色
    if data.role is not None and not current_user.is_super_admin():
        logger.warning(
            f"User update failed: User {current_user.username} tried to change role of user {target_user.username}")
        return HttpResponse.forbidden("只有超级管理员可以更改用户角色")

    # 更新字段
    if data.role is not None:
        target_user.role = data.role
    if data.is_locked is not None:
        target_user.is_locked = data.is_locked

    target_user.save()
    logger.info(f"Admin {current_user.username} updated user {target_user.username}")

    return HttpResponse.ok()


@admin_bp.route('/admin/users/reset_password', methods=['POST'])
@jwt_required()
@admin_required()
@validate_request(AdminPasswordResetSchema)
def reset_user_password():
    """重置用户密码"""
    data = get_validated_data(AdminPasswordResetSchema)

    target_user = UserModel.query.get(data.user_id)
    if not target_user:
        logger.warning(f"User reset password failed: User with ID {data.user_id} does not exist")
        return HttpResponse.not_found("用户不存在")

    # 权限检查：只有超级管理员可以重置其他管理员的密码
    if target_user.is_admin() and not current_user.is_super_admin():
        logger.warning(
            f"User reset password failed: User {current_user.username} tried to reset password for admin user {target_user.username}")
        return HttpResponse.forbidden("只有超级管理员可以重置管理员用户的密码")

    # 防止重置自己的密码（建议管理员使用正常修改密码功能）
    if target_user.user_id == current_user.user_id:
        logger.warning(
            f"User reset password failed: User {current_user.username} tried to reset their own password")
        return HttpResponse.fail("不能重置自己的密码，请使用修改密码功能")

    # 重置密码
    target_user.reset_password(data.new_password)
    logger.info(f"Admin {current_user.username} reset password for user {target_user.username}")
    return HttpResponse.ok(f"用户 {target_user.username} 的密码已重置为 {data.new_password}")


@admin_bp.route('/admin/users/delete', methods=['POST'])
@jwt_required()
@admin_required()
@validate_request(AdminUserDeleteSchema)
def delete_user():
    """软删除用户"""
    data = get_validated_data(AdminUserDeleteSchema)

    target_user = UserModel.query.get(data.user_id)
    if not target_user:
        logger.warning(f"User delete failed: User with ID {data.user_id} does not exist")
        return HttpResponse.not_found("用户不存在")

    # 检查用户是否已经被删除
    if target_user.is_deleted:
        logger.warning(f"User delete failed: User {target_user.username} is already deleted")
        return HttpResponse.fail("用户已经被删除")

    # 权限检查：只有超级管理员可以删除其他管理员
    if target_user.is_admin() and not current_user.is_super_admin():
        logger.warning(
            f"User delete failed: User {current_user.username} tried to delete admin user {target_user.username}")
        return HttpResponse.forbidden("只有超级管理员可以删除管理员用户")

    # 防止删除自己
    if target_user.user_id == current_user.user_id:
        logger.warning(f"User delete failed: User {current_user.username} tried to delete their own account")
        return HttpResponse.fail("不能删除自己的账户")

    # 软删除用户
    target_user.soft_delete()
    logger.info(f"Admin {current_user.username} deleted user {target_user.username}")
    return HttpResponse.ok(f"用户 {target_user.username} 已被删除")


@admin_bp.route('/admin/users/restore', methods=['POST'])
@jwt_required()
@admin_required()
@validate_request(AdminUserRestoreSchema)
def restore_user():
    """恢复被删除的用户"""
    data = get_validated_data(AdminUserRestoreSchema)

    target_user = UserModel.query.get(data.user_id)
    if not target_user:
        logger.warning(f"User restore failed: User with ID {data.user_id} does not exist")
        return HttpResponse.not_found("用户不存在")

    # 检查用户是否已经被删除
    if not target_user.is_deleted:
        logger.warning(f"User restore failed: User {target_user.username} is not deleted")
        return HttpResponse.fail("用户未被删除，无需恢复")

    # 权限检查：只有超级管理员可以恢复管理员用户
    if target_user.is_admin() and not current_user.is_super_admin():
        logger.warning(
            f"User restore failed: User {current_user.username} tried to restore admin user {target_user.username}")
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

    logger.info(f"Admin {current_user.username} restored user {target_user.username}")
    return HttpResponse.ok(f"用户 {target_user.username} 已被恢复")


@admin_bp.route('/admin/tasks', methods=['GET'])
@jwt_required()
@admin_required()
@validate_request(AdminTaskListSchema)
def get_tasks():
    """获取任务列表"""
    data = get_validated_data(AdminTaskListSchema)
    # 使用JOIN查询来支持用户名筛选和避免N+1查询问题
    query = db.session.query(TaskModel, UserModel).join(UserModel, TaskModel.user_id == UserModel.user_id)

    # 用户名筛选
    if data.username:
        query = query.filter(UserModel.username.contains(data.username))

    # 状态筛选
    if data.status:
        query = query.filter(TaskModel.task_status == data.status)

    # 比赛筛选
    if data.cname:
        query = query.filter(TaskModel.cname == data.cname)

    # trace文件筛选
    if data.trace_file:
        # 按trace文件名筛选（支持模糊匹配）
        query = query.filter(TaskModel.trace_name.contains(data.trace_file))

    # 排序
    if data.sort_by == 'score':
        # 按分数排序
        if data.sort_order == 'asc':
            query = query.order_by(TaskModel.task_score.asc())
        else:
            query = query.order_by(TaskModel.task_score.desc())
    else:
        # 默认按创建时间排序
        if data.sort_order == 'asc':
            query = query.order_by(TaskModel.created_time.asc())
        else:
            query = query.order_by(TaskModel.created_time.desc())

    # 分页
    total = query.count()
    results = query.offset((data.page - 1) * data.size).limit(data.size).all()

    # 构建任务列表
    task_list = []
    for task, user in results:
        task_dict = task.to_detail_dict(current_user.is_admin())  # 传递当前用户（管理员）
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


@cache.memoize(timeout=30)
def _get_general_stats():
    """获取通用统计信息的缓存函数（不依赖课程）"""
    user_stats = {
        'total_users': UserModel.query.filter_by(is_deleted=False).count(),
        'deleted_users': UserModel.query.filter_by(is_deleted=True).count()
    }

    # 任务状态统计（所有课程）
    all_course_task_stats = {
        'total': TaskModel.query.count(),
        # 计算今日提交数（通过统计今天创建的不同upload_id数量）
        'today_submit': TaskModel.query.filter(
            db.func.date(TaskModel.created_time) == date.today()
        ).with_entities(TaskModel.upload_id).distinct().count()
    }
    for status in TaskStatus:
        count = TaskModel.query.filter(TaskModel.task_status == status.value).count()
        all_course_task_stats[status.value] = count

    # 添加过去10天每天的提交数量（所有课程）
    daily_submissions = []
    for i in range(10):
        target_date = date.today() - timedelta(days=i)
        daily_count = TaskModel.query.filter(
            db.func.date(TaskModel.created_time) == target_date
        ).with_entities(TaskModel.upload_id).distinct().count()
        daily_submissions.append({
            'date': target_date.strftime('%Y-%m-%d'),
            'count': daily_count
        })
    all_course_task_stats['daily_submissions'] = daily_submissions

    # 比赛参与统计
    competition_stats = {}
    for course_name in config.Course.CNAME_LIST:
        participant_count = CompetitionModel.query.filter(CompetitionModel.cname == course_name).count()
        competition_stats[course_name] = participant_count

    # 角色统计（仅统计未删除用户）
    role_stats = {}
    for role in UserRole:
        count = UserModel.query.filter(UserModel.role == role.value, UserModel.is_deleted == False).count()
        role_stats[role.value] = count

    logger.info("General stats fetched successfully")

    return {
        'user_stats': user_stats,
        'all_course_task_stats': all_course_task_stats,
        'competition_stats': competition_stats,
        'role_stats': role_stats
    }


@cache.memoize(timeout=30)
def _get_course_specific_stats(cname):
    """根据课程名称获取课程特定统计信息的缓存函数"""
    # 本课程任务统计
    current_course_task_stats = {}

    # 统计当前课程各状态的任务数量
    for status in TaskStatus:
        count = TaskModel.query.filter(
            TaskModel.cname == cname,
            TaskModel.task_status == status.value
        ).count()
        current_course_task_stats[status.value] = count

    # 统计当前课程的总任务数
    current_course_task_stats['total'] = TaskModel.query.filter(TaskModel.cname == cname).count()

    # 统计当前课程今日提交数
    current_course_task_stats['today_submit'] = TaskModel.query.filter(
        TaskModel.cname == cname,
        db.func.date(TaskModel.created_time) == date.today()
    ).with_entities(TaskModel.upload_id).distinct().count()

    # 添加过去10天每天的提交数量（当前课程）
    current_course_daily_submissions = []
    for i in range(10):
        target_date = date.today() - timedelta(days=i)
        daily_count = TaskModel.query.filter(
            TaskModel.cname == cname,
            db.func.date(TaskModel.created_time) == target_date
        ).with_entities(TaskModel.upload_id).distinct().count()
        current_course_daily_submissions.append({
            'date': target_date.strftime('%Y-%m-%d'),
            'count': daily_count
        })
    current_course_task_stats['daily_submissions'] = current_course_daily_submissions
    logger.info(f"Course-specific stats for {cname} fetched successfully")
    return {
        'current_course_task_stats': current_course_task_stats
    }


@admin_bp.route('/admin/stats', methods=['GET'])
@jwt_required()
@admin_required()
def get_stats():
    """获取系统统计信息"""
    cname = get_jwt().get('cname')
    # 获取通用统计信息（全局缓存）
    general_stats = _get_general_stats()
    # 获取课程特定统计信息（按课程缓存）
    course_stats = _get_course_specific_stats(cname)
    # 合并两个统计结果
    stats_data = {**general_stats, **course_stats}
    logger.info(f"Admin {current_user.username} fetched system stats for course {cname}")
    return HttpResponse.ok(data=stats_data)


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
    process_name_list = ['gunicorn', 'dramatiq', 'run.py', 'sender', 'receiver']
    for proc in psutil.process_iter(['pid', 'name', 'create_time', 'cmdline']):
        try:
            if proc.info['cmdline'] and any(
                    any(process_name in cmd for process_name in process_name_list) for cmd in proc.info['cmdline']):
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
    logger.info(f"Found {len(related_processes)} related processes")
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
                'related_processes': related_processes,
                'current_process': {
                    'current_pid': os.getpid(),
                    'start_time': process_start_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'uptime_formatted': str(process_uptime).split('.')[0],  # 去掉微秒显示
                }
            },
            'config': {
                'courses': config.Course.CNAME_LIST,
                'register_student_list': config.Course.REGISTER_STUDENT_LIST,
                'course_detail': config.Course.ALL_CLASS,
                'log_level': config.Logging.LOG_LEVEL,
                'debug': current_app.debug,
                'env': os.getenv('APP_ENV', 'development')
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
        logger.error(f"Log directory {log_dir} does not exist")
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
    logger.debug(f"Admin {current_user.username} fetched log files, count: {len(log_files)}")
    return HttpResponse.ok(data={'log_files': log_files, 'log_dir': log_dir})


@admin_bp.route('/admin/system/logs/stream/<log_name>', methods=['GET'])
@jwt_required()
@admin_required()
def stream_log_file(log_name):
    """流式获取日志内容（Server-Sent Events）"""
    # 验证日志文件
    is_valid, log_path, error_response = _validate_log_file(log_name)
    if not is_valid:
        return error_response

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
    logger.info(f"Admin {current_user.username} streaming log file: {log_name}")
    return Response(stream_with_context(generate()), headers=headers)


@admin_bp.route('/admin/system/logs/download/<log_name>', methods=['GET'])
@jwt_required()
@admin_required()
def download_log_file(log_name):
    """下载日志文件"""
    # 验证日志文件
    is_valid, log_path, error_response = _validate_log_file(log_name)
    if not is_valid:
        return error_response

    logger.info(f"Admin {current_user.username} downloading log file: {log_name}")
    return HttpResponse.send_attachment_file(log_path)
