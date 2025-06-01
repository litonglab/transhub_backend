# 参数校验器使用文档

## 简介

本项目使用 Pydantic 框架实现了一个统一的参数校验机制，通过装饰器模式简化了参数验证的流程。该机制可以：

- 自动验证请求参数的类型和格式
- 提供友好的错误提示
- 减少重复的验证代码
- 提高代码的可维护性
- 增强类型安全性

## 使用方法

### 1. 定义验证模型

在 `schemas.py` 中定义 Pydantic 模型，例如：

```python
from pydantic import BaseModel, Field, validator


class UserLoginSchema(BaseModel):
    """用户登录请求参数验证"""
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

在视图函数上添加 `@validate_request` 装饰器：

```python
from app_backend.decorators.validators import validate_request
from app_backend.validators.schemas import UserLoginSchema


@user_bp.route('/user_login', methods=['POST'])
@validate_request(UserLoginSchema)
def user_login():
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

## 示例

### 用户注册接口

```python
@user_bp.route('/user_register', methods=['POST'])
@validate_request(UserRegisterSchema)
def user_register():
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

### 获取任务信息接口

```python
@task_bp.route("/task_get_task_info", methods=["POST"])
@jwt_required()
@validate_request(TaskInfoSchema)
def return_task():
    data = get_validated_data(TaskInfoSchema)
    task_id = data.task_id
    user_id = get_jwt_identity()

    # 业务逻辑处理
    task_info = Task_model.query.filter_by(task_id=task_id).first()
    return myResponse(200, "Task info found.", task_res=task_info.to_dict())
```
