"""
请求参数验证装饰器
"""
from functools import wraps
from typing import TypeVar, Type, Callable, Any, cast

from flask import request
from pydantic import BaseModel, ValidationError

from app_backend.vo import HttpResponse

# 定义泛型类型变量
T = TypeVar('T', bound=BaseModel)


def validate_request(schema_class: Type[T]) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    请求参数验证装饰器，支持类型提示

    :param schema_class: Pydantic 验证模型类
    :return: 装饰器函数

    使用示例:
        @validate_request(UserLoginSchema)
        def login():
            data = request.validated_data  # 类型为 UserLoginSchema
            # 编辑器会提供完整的类型提示
            username = data.username
            password = data.password
    """

    def decorator(f: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                # 获取请求数据
                if request.is_json:
                    data = request.get_json() or {}
                else:
                    data = request.form.to_dict()

                # 检查是否有文件上传
                files = {}
                if request.files:
                    for key, file in request.files.items():
                        files[key] = file

                # 合并表单数据和文件数据
                all_data = {**data, **files}

                # 验证数据并创建类型化实例
                validated_data: T = schema_class(**all_data)

                # 将验证后的数据添加到请求对象中，并保持类型信息
                request.validated_data = validated_data

                return f(*args, **kwargs)
            except ValidationError as e:
                # 处理验证错误
                error_messages = []
                for error in e.errors():
                    field = error.get('loc', [''])[0]
                    message = error.get('msg', '')
                    error_messages.append(f"{field}: {message}")

                return HttpResponse.fail(f"参数验证失败: {error_messages}")
            except Exception as e:
                return HttpResponse.error(500, f"服务器内部错误: {str(e)}")

        return decorated_function

    return decorator


def get_validated_data(schema_class: Type[T]) -> T:
    """
    获取已验证的数据，带有完整的类型提示

    :param schema_class: 期望的 Schema 类型
    :return: 类型化的验证数据

    使用示例:
        @validate_request(UserLoginSchema)
        def login():
            data = get_validated_data(UserLoginSchema)  # 类型为 UserLoginSchema
            username = data.username  # 编辑器提供类型提示
    """
    if not hasattr(request, 'validated_data'):
        raise RuntimeError("No validated data found. Make sure to use @validate_request decorator first.")

    # 验证类型匹配
    validated_data = request.validated_data
    if not isinstance(validated_data, schema_class):
        raise TypeError(f"Expected {schema_class.__name__}, got {type(validated_data).__name__}")

    # 使用 cast 来告诉类型检查器这是正确的类型
    return cast(T, validated_data)
