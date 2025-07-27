"""
请求参数验证装饰器
"""
import logging
from functools import wraps
from typing import TypeVar, Type, Callable, Any, cast

from flask import request
from pydantic import BaseModel, ValidationError

from app_backend.vo.http_response import HttpResponse

# 定义泛型类型变量
T = TypeVar('T', bound=BaseModel)

logger = logging.getLogger(__name__)


def validate_request(schema_class: Type[T]) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    请求参数验证装饰器，支持类型提示

    :param schema_class: Pydantic 验证模型类
    :return: 装饰器函数

    支持的请求类型：
    - GET请求：从URL参数（query parameters）中获取数据
    - POST/PUT/PATCH请求：支持JSON格式和表单格式的请求体数据
    - 文件上传：支持multipart/form-data格式的文件上传（仅非GET请求）

    使用示例:
        # GET请求示例
        @validate_request(UserQuerySchema)
        def get_users():
            data = request.validated_data  # 类型为 UserQuerySchema
            # 从URL参数获取: /users?page=1&size=10
            page = data.page
            size = data.size
            
        # POST请求示例
        @validate_request(UserLoginSchema)
        def login():
            data = request.validated_data  # 类型为 UserLoginSchema
            # 编辑器会提供完整的类型提示
            username = data.username
            password = data.password
    """
    logger.debug(f"Creating validation decorator for schema: {schema_class.__name__}")

    def decorator(f: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                # 获取请求数据，并根据请求类型处理
                if request.method == 'GET':
                    # GET请求：获取URL参数
                    logger.debug("Processing GET request URL parameters")
                    data = request.args.to_dict()
                elif request.is_json:
                    # POST/PUT/PATCH请求：JSON数据
                    logger.debug("Processing JSON request data")
                    data = request.get_json() or {}
                else:
                    # POST/PUT/PATCH请求：表单数据
                    logger.debug("Processing form request data")
                    data = request.form.to_dict()

                # 检查是否有文件上传（仅对非GET请求）
                files = {}
                if request.method != 'GET' and request.files:
                    logger.debug(f"Processing file uploads: {list(request.files.keys())}")
                    for key, file in request.files.items():
                        files[key] = file

                # 合并所有数据
                all_data = {**data, **files}
                logger.debug(f"Combined request data keys: {list(all_data.keys())}")

                # 验证数据并创建类型化实例
                validated_data: T = schema_class(**all_data)

                # 将验证后的数据添加到请求对象中，并保持类型信息
                request.validated_data = validated_data
                logger.debug("Request data validation successful")
            except ValidationError as e:
                # 处理验证错误
                logger.warning(f"Validation error in {f.__name__}: {str(e)}")
                error_messages = []
                for error in e.errors():
                    field = error.get('loc', [''])[0]
                    message = error.get('msg', '')
                    error_messages.append(f"{field}: {message}")
                    logger.debug(f"Validation error - Field: {field}, Message: {message}")

                error_messages = ', '.join(error_messages[:3])  # 限制错误信息数量，避免过长
                return HttpResponse.fail(f"参数校验失败: {error_messages}")
            except Exception as e:
                logger.error(f"Unexpected error in {f.__name__}: {str(e)}", exc_info=True)
                # 返回通用错误响应
                return HttpResponse.internal_error("参数校验失败，请稍后重试")

            return f(*args, **kwargs)

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
        logger.error("No validated data found in request")
        raise RuntimeError("No validated data found. Make sure to use @validate_request decorator first.")

    # 验证类型匹配
    validated_data = request.validated_data
    if not isinstance(validated_data, schema_class):
        logger.error(f"Type mismatch: Expected {schema_class.__name__}, got {type(validated_data).__name__}")
        raise TypeError(f"Expected {schema_class.__name__}, got {type(validated_data).__name__}")

    # 使用 cast 来告诉类型检查器这是正确的类型
    return cast(T, validated_data)
