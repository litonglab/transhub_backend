"""
请求参数验证装饰器
"""
from functools import wraps

from flask import request
from pydantic import ValidationError

from app_backend.vo.response import myResponse


def validate_request(schema_class):
    """
    请求参数验证装饰器
    :param schema_class: Pydantic 验证模型类
    :return: 装饰器函数
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                # 获取请求数据
                if request.is_json:
                    data = request.get_json()
                else:
                    data = request.form.to_dict()

                # 检查是否有文件上传
                files = {}
                if request.files:
                    for key, file in request.files.items():
                        files[key] = file

                # 合并表单数据和文件数据
                all_data = {**data, **files}

                # 验证数据
                validated_data = schema_class(**all_data)

                # 将验证后的数据添加到请求对象中
                request.validated_data = validated_data

                return f(*args, **kwargs)
            except ValidationError as e:
                # 处理验证错误
                error_messages = []
                for error in e.errors():
                    field = error.get('loc', [''])[0]
                    message = error.get('msg', '')
                    error_messages.append(f"{field}: {message}")

                return myResponse(400, f"参数验证失败: {error_messages}")  # , errors=error_messages)
            except Exception as e:
                return myResponse(500, f"服务器内部错误: {str(e)}")

        return decorated_function

    return decorator
