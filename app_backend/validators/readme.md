# 参数校验器使用文档

## 简介

本项目使用 Pydantic 框架实现了一个统一的参数校验机制，通过装饰器模式简化了参数验证的流程。该机制可以：

- 自动验证请求参数的类型和格式
- 支持多种请求类型：GET（URL参数）、POST/PUT/PATCH（JSON/表单数据）
- 提供友好的错误提示
- 减少重复的验证代码
- 提高代码的可维护性
- 增强类型安全性

## 使用方法

### 1. 定义验证模型

在 `schemas.py` 中定义 Pydantic 模型，支持不同类型的请求：

#### GET请求参数验证模型
```python
from pydantic import BaseModel, Field
from typing import Optional


class UserQuerySchema(BaseModel):
    """用户查询请求参数验证（GET请求）"""
    page: int = Field(default=1, ge=1, description="页码，从1开始")
    size: int = Field(default=10, ge=1, le=100, description="每页大小，1-100")
    keyword: Optional[str] = Field(default="", description="搜索关键词")
    active: bool = Field(default=True, description="是否只查询活跃用户")
    sort_by: Optional[str] = Field(default="created_at", description="排序字段")
```

#### POST请求参数验证模型
```python
class UserLoginSchema(BaseModel):
    """用户登录请求参数验证（POST请求）"""
    username: str = Field(..., min_length=4, max_length=16, description="用户名，4-16个字符")
    password: str = Field(..., min_length=6, max_length=18, description="密码，6-18个字符")
    cname: Optional[str] = Field(None, description="比赛名称")

    @field_validator('username')
    def validate_username(cls, v):
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError('用户名只能包含字母、数字和下划线')
        return v
```

### 2. 使用装饰器

在视图函数上添加 `@validate_request` 装饰器，支持多种HTTP方法：

#### GET请求示例
```python
from app_backend.validators.decorators import validate_request
from app_backend.validators.schemas import UserQuerySchema


@user_bp.route('/users', methods=['GET'])
@validate_request(UserQuerySchema)
def get_users():
    """
    获取用户列表
    URL示例: /users?page=2&size=20&keyword=admin&active=true
    """
    data = get_validated_data(UserQuerySchema)
    page = data.page          # int类型，已验证范围
    size = data.size          # int类型，已验证范围
    keyword = data.keyword    # str类型
    active = data.active      # bool类型，自动转换
    
    # ... 后续业务逻辑
    return {"users": [], "pagination": {"page": page, "size": size}}
```

#### POST请求示例
```python
from app_backend.validators.decorators import validate_request
from app_backend.validators.schemas import UserLoginSchema


@user_bp.route('/user_login', methods=['POST'])
@validate_request(UserLoginSchema)
def user_login():
    """
    用户登录
    支持JSON和表单数据提交
    """
    data = get_validated_data(UserLoginSchema)
    username = data.username
    password = data.password
    cname = data.cname
    # ... 后续业务逻辑
```

### 3. 获取验证后的数据

通过 `get_validated_data` 获取验证后的数据：

```python
data = get_validated_data(Schema)
# 直接访问验证后的字段
username = data.username
password = data.password
```

## 支持的请求类型

### 1. GET请求（URL参数）
- 从URL查询参数中获取数据：`/api/users?page=1&size=10&keyword=admin`
- 支持自动类型转换（字符串转整数、布尔值等）
- 适用于查询、筛选、分页等场景

### 2. POST/PUT/PATCH请求（请求体数据）
- **JSON格式**：`Content-Type: application/json`
- **表单格式**：`Content-Type: application/x-www-form-urlencoded`
- **文件上传**：`Content-Type: multipart/form-data`

### 3. 数据处理优先级
1. GET请求：仅处理URL参数
2. 非GET请求：
   - 优先处理JSON数据（如果Content-Type为application/json）
   - 其次处理表单数据
   - 合并文件上传数据（如果存在）

## 验证规则

### 1. 基本类型验证

```python
class ExampleSchema(BaseModel):
    # 必填字段
    required_field: str = Field(..., description="必填字段")

    # 可选字段
    optional_field: Optional[str] = Field(None, description="可选字段")

    # 带默认值的字段
    default_field: str = Field("default", description="带默认值的字段")
```

### 2. 字段约束

```python
class ExampleSchema(BaseModel):
    # 字符串长度限制
    name: str = Field(..., min_length=1, max_length=50)

    # 数值范围限制
    age: int = Field(..., ge=0, le=150)

    # 正则表达式验证
    email: str = Field(..., regex=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
```

### 3. 自定义验证器

```python
class ExampleSchema(BaseModel):
    field: str

    @validator('field')
    def validate_field(cls, v):
        if not v.strip():
            raise ValueError('字段不能为空')
        return v.strip()
```

## 错误处理

当参数验证失败时，装饰器会自动返回错误信息：

```json
{
	"code": 400,
	"message": "参数验证失败",
	"errors": [
		"username: 用户名只能包含字母、数字和下划线",
		"password: 密码长度必须在6-18个字符之间"
	]
}
```

## 最佳实践

1. 为每个接口创建独立的验证模型
2. 使用有意义的字段名称和描述
3. 合理使用验证器进行复杂的验证
4. 保持验证规则的简单性和可维护性
5. 在模型类中添加详细的文档字符串

## 注意事项

1. 验证器装饰器应该放在路由装饰器之后
2. 对于文件上传等特殊请求，可能需要自定义验证逻辑
3. 验证失败时会自动返回错误响应，不需要手动处理验证错误
4. 验证后的数据会自动进行类型转换

## 完整示例

### GET请求示例：用户列表查询

```python
from pydantic import BaseModel, Field
from typing import Optional


class UserListQuerySchema(BaseModel):
    """用户列表查询参数"""
    page: int = Field(default=1, ge=1, description="页码")
    size: int = Field(default=10, ge=1, le=100, description="每页大小")
    keyword: Optional[str] = Field(default="", description="用户名关键词")
    role: Optional[str] = Field(default=None, description="用户角色筛选")
    active: bool = Field(default=True, description="是否只显示活跃用户")
    sort_by: str = Field(default="created_at", description="排序字段")
    order: str = Field(default="desc", regex="^(asc|desc)$", description="排序方向")


@user_bp.route('/users', methods=['GET'])
@validate_request(UserListQuerySchema)
def get_users():
    """
    获取用户列表
    URL示例: /users?page=2&size=20&keyword=john&role=admin&active=true&sort_by=username&order=asc
    """
    data = get_validated_data(UserListQuerySchema)
    
    # 所有参数都已经过验证和类型转换
    page = data.page        # int, >= 1
    size = data.size        # int, 1-100 之间
    keyword = data.keyword  # str, 可能为空字符串
    role = data.role       # Optional[str], 可能为 None
    active = data.active   # bool, 自动从字符串转换
    sort_by = data.sort_by # str, 默认值 "created_at"
    order = data.order     # str, 只能是 "asc" 或 "desc"
    
    # 构建查询
    query = User.query
    if keyword:
        query = query.filter(User.username.contains(keyword))
    if role:
        query = query.filter(User.role == role)
    if active:
        query = query.filter(User.active == True)
    
    # 分页和排序
    total = query.count()
    users = query.order_by(getattr(User, sort_by).desc() if order == 'desc' 
                          else getattr(User, sort_by).asc()) \
                 .offset((page - 1) * size) \
                 .limit(size) \
                 .all()
    
    return {
        "users": [user.to_dict() for user in users],
        "pagination": {
            "page": page,
            "size": size,
            "total": total,
            "pages": (total + size - 1) // size
        }
    }
```

### POST请求示例：用户注册接口

```python
class UserRegisterSchema(BaseModel):
    """用户注册参数验证"""
    username: str = Field(..., min_length=4, max_length=16, description="用户名")
    password: str = Field(..., min_length=6, max_length=18, description="密码")
    real_name: str = Field(..., min_length=1, max_length=50, description="真实姓名")
    sno: str = Field(..., description="学号")
    
    @field_validator('username')
    def validate_username(cls, v):
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError('用户名只能包含字母、数字和下划线')
        return v


@user_bp.route('/user_register', methods=['POST'])
@validate_request(UserRegisterSchema)
def user_register():
    """用户注册（支持JSON和表单提交）"""
    data = get_validated_data(UserRegisterSchema)
    username = data.username
    password = data.password
    real_name = data.real_name
    sno = data.sno

    # 业务逻辑处理
    user = User_model(username=username, password=password,
                      real_name=real_name, sno=sno)
    user.save()
    return myResponse(200, "Register success.")
```

### 混合请求示例：任务管理

```python
# GET请求：获取任务列表
class TaskListQuerySchema(BaseModel):
    """任务列表查询参数"""
    status: Optional[str] = Field(default=None, description="任务状态筛选")
    page: int = Field(default=1, ge=1, description="页码")
    size: int = Field(default=10, ge=1, le=50, description="每页大小")


@task_bp.route("/tasks", methods=["GET"])
@jwt_required()
@validate_request(TaskListQuerySchema)
def get_tasks():
    """获取任务列表"""
    data = get_validated_data(TaskListQuerySchema)
    user_id = get_jwt_identity()
    
    # 使用验证后的参数查询任务
    tasks = Task_model.query.filter_by(user_id=user_id)
    if data.status:
        tasks = tasks.filter_by(status=data.status)
    
    total = tasks.count()
    tasks = tasks.offset((data.page - 1) * data.size).limit(data.size).all()
    
    return myResponse(200, "Tasks found.", 
                     tasks=[task.to_dict() for task in tasks],
                     pagination={"page": data.page, "size": data.size, "total": total})


# POST请求：获取特定任务信息
class TaskInfoSchema(BaseModel):
    """任务信息查询参数"""
    task_id: int = Field(..., ge=1, description="任务ID")


@task_bp.route("/task_get_task_info", methods=["POST"])
@jwt_required()
@validate_request(TaskInfoSchema)
def return_task():
    """获取任务详细信息"""
    data = get_validated_data(TaskInfoSchema)
    task_id = data.task_id
    user_id = get_jwt_identity()

    # 业务逻辑处理
    task_info = Task_model.query.filter_by(task_id=task_id).first()
    return myResponse(200, "Task info found.", task_res=task_info.to_dict())
```

## 类型转换说明

装饰器会自动进行类型转换，特别是对于GET请求的URL参数：

```python
# URL: /api/users?page=2&active=true&tags=python,flask
class QuerySchema(BaseModel):
    page: int = Field(default=1)        # "2" -> 2
    active: bool = Field(default=False) # "true" -> True
    tags: List[str] = Field(default=[]) # "python,flask" -> ["python", "flask"]
    score: Optional[float] = None       # "3.14" -> 3.14
```

## 错误处理增强

装饰器现在对不同请求类型提供更准确的错误信息：

```json
{
    "code": 400,
    "message": "参数校验失败: page: 页码必须大于等于1, size: 每页大小必须在1到100之间",
    "data": null
}
```

## 注意事项更新

1. **请求方法识别**：装饰器会自动识别请求方法并选择合适的数据源
2. **GET请求限制**：GET请求不支持文件上传，文件上传仅适用于POST等方法
3. **类型转换**：URL参数会自动进行类型转换，但复杂类型（如列表、对象）需要特殊处理
4. **参数编码**：URL参数需要正确编码，特别是包含特殊字符的参数
5. **长度限制**：URL参数有长度限制，复杂数据建议使用POST请求

## 最佳实践更新

1. **选择合适的请求方法**：
   - GET：用于查询、筛选、分页等只读操作
   - POST：用于创建、登录等需要发送敏感数据的操作
   - PUT/PATCH：用于更新操作

2. **参数设计**：
   - GET请求参数保持简单，避免复杂嵌套结构
   - 为查询参数提供合理的默认值
   - 使用枚举验证限制参数值的范围

3. **错误处理**：
   - 提供清晰的字段描述，便于生成有意义的错误信息
   - 对重要字段使用自定义验证器进行额外检查
