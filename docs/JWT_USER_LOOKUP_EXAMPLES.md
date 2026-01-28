# JWT User Lookup Loader 使用示例

## 在其他视图中使用 current_user

现在你可以在任何需要获取当前用户的地方直接使用`current_user`：

### 示例 1：用户视图中使用

```python
from flask_jwt_extended import jwt_required, current_user
from app_backend.vo.http_response import HttpResponse

@user_bp.route('/user/profile', methods=['GET'])
@jwt_required()
def get_user_profile():
    """获取用户个人信息"""
    user = current_user  # 自动加载，已包含安全检查

    if not user:
        return HttpResponse.not_authorized('用户不存在或账户已被禁用')

    # 直接使用user对象，无需手动查询
    return HttpResponse.ok(data=user.to_dict())

@user_bp.route('/user/change_password', methods=['POST'])
@jwt_required()
@validate_request(ChangePasswordSchema)
def change_password():
    """修改密码"""
    data = get_validated_data(ChangePasswordSchema)
    user = current_user  # 自动加载

    if not user:
        return HttpResponse.not_authorized('用户不存在或账户已被禁用')

    # 验证旧密码
    if not user.check_password(data.old_pwd):
        return HttpResponse.fail('旧密码错误')

    # 设置新密码
    user.set_password(data.new_pwd)
    user.save()

    return HttpResponse.ok('密码修改成功')
```

### 示例 2：任务视图中使用

```python
@task_bp.route('/task/submit', methods=['POST'])
@jwt_required()
@validate_request(TaskSubmitSchema)
def submit_task():
    """提交任务"""
    data = get_validated_data(TaskSubmitSchema)
    user = current_user  # 自动加载

    if not user:
        return HttpResponse.not_authorized('用户不存在或账户已被禁用')

    # 创建任务，直接使用user对象
    task = TaskModel(
        user_id=user.user_id,
        cname=data.cname,
        # ...其他字段
    )
    task.save()

    logger.info(f"User {user.username} submitted task {task.task_id}")

    return HttpResponse.ok('任务提交成功')
```

### 示例 3：自定义权限装饰器

```python
def course_access_required(cname):
    """课程访问权限装饰器"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = current_user

            if not user:
                return HttpResponse.not_authorized('用户不存在或账户已被禁用')

            # 检查用户是否有访问该课程的权限
            if not user.has_course_access(cname):
                return HttpResponse.forbidden(f'无权访问课程 {cname}')

            return f(*args, **kwargs)
        return decorated_function
    return decorator

# 使用示例
@task_bp.route('/course/<cname>/tasks', methods=['GET'])
@jwt_required()
@course_access_required('algorithms')
def get_course_tasks(cname):
    user = current_user  # 已经通过装饰器验证

    # 获取用户在该课程的任务
    tasks = TaskModel.query.filter_by(
        user_id=user.user_id,
        cname=cname
    ).all()

    return HttpResponse.ok(data=[task.to_dict() for task in tasks])
```

## 与 dramatiq_auth 中间件的结合

如果要在 dramatiq_auth 中间件中使用相同的逻辑：

```python
from app_backend.security.auth import user_lookup_callback

def validate_admin_access(token):
    """验证JWT token并检查管理员权限"""
    try:
        # 解码JWT token
        decoded_token = decode_token(token)

        # 使用相同的user_lookup逻辑
        user = user_lookup_callback(None, decoded_token)

        if not user:
            return False, "User not found, deleted, or locked"

        if not user.is_admin():
            return False, "Admin privileges required"

        return True, f"Access granted for admin user {user.username}"

    except Exception as e:
        return False, f"Authentication error: {str(e)}"
```

## 性能考虑

### 请求缓存

Flask-JWT-Extended 会在单个请求内缓存 user_lookup 的结果，所以在同一个请求中多次调用`current_user`不会触发多次数据库查询。

### 数据库优化

如果需要优化性能，可以考虑：

1. **添加数据库索引**：确保 user_id 字段有索引
2. **使用 Redis 缓存**：缓存用户信息，减少数据库查询
3. **选择性加载**：只加载必要的用户字段

```python
@jwt.user_lookup_loader
def user_lookup_callback(_jwt_header, jwt_data):
    """优化版本：使用选择性加载"""
    try:
        user_id = jwt_data.get('sub')
        if not user_id:
            return None

        # 只加载必要字段，减少数据传输
        user = UserModel.query.options(
            load_only('user_id', 'username', 'role', 'is_deleted', 'is_locked')
        ).get(user_id)

        if not user or user.is_deleted or user.is_locked:
            return None

        return user

    except Exception as e:
        logger.error(f"Error loading user from JWT: {e}")
        return None
```

## 调试和监控

### 日志记录

user_lookup_loader 已经包含了详细的日志记录：

```python
# 成功加载用户
logger.debug(f"Successfully loaded user: {user.username} (ID: {user_id})")

# 用户不存在
logger.warning(f"User not found in database for ID: {user_id}")

# 用户被删除
logger.warning(f"User {user.username} (ID: {user_id}) has been deleted")

# 用户被锁定
logger.warning(f"User {user.username} (ID: {user_id}) is locked")
```

### 监控指标

可以添加监控来跟踪：

- user_lookup 成功/失败的比率
- 被删除/锁定用户的访问尝试次数
- 数据库查询性能

这个实现为整个系统提供了统一、安全、高效的用户认证机制。
