from flask import jsonify, send_file, make_response
from flask_jwt_extended import create_access_token, set_access_cookies, unset_jwt_cookies

from app_backend import get_default_config


class HttpResponse:
    """
    HTTP响应类，用于统一管理API响应格式
    """

    def __init__(self, code=200, message='', **kwargs):
        """
        初始化HTTP响应
        
        Args:
            code (int): 响应状态码
            message (str): 响应消息
            **kwargs: 其他响应数据
        """
        self.code = code
        self.message = message
        self.data = kwargs

    def to_dict(self):
        """
        将响应转换为字典格式
        
        Returns:
            dict: 响应字典
        """
        response = {
            'code': self.code,
            'message': self.message
        }
        response.update(self.data)
        return response

    def to_json(self):
        """
        将响应转换为JSON格式
        
        Returns:
            flask.Response: Flask JSON响应对象
        """
        return jsonify(self.to_dict())

    @classmethod
    def ok(cls, message='success', **kwargs):
        """
        返回成功响应（状态码200）
        
        Args:
            message (str): 响应消息
            **kwargs: 其他响应数据
            
        Returns:
            flask.Response: Flask JSON响应对象
        """
        return cls(code=200, message=message, **kwargs).to_json()

    @classmethod
    def login_success(cls, user_id, additional_claims=None, max_age=None, **kwargs):
        """
        返回登录成功响应，自动生成JWT token并设置到cookie中
        
        Args:
            user_id (str): 用户ID
            additional_claims (dict): JWT中的额外声明
            max_age (int): cookie的最大存活时间（秒），默认使用配置文件中的值
            **kwargs: 其他响应数据
            
        Returns:
            flask.Response: 包含JWT cookie的Flask响应对象
        """
        # 如果没有指定max_age，使用配置文件中的默认值
        if max_age is None:
            config = get_default_config()
            max_age = config.Security.JWT_ACCESS_TOKEN_EXPIRES
        # 生成JWT token
        access_token = create_access_token(
            identity=user_id,
            additional_claims=additional_claims or {}
        )
        resp = make_response(cls.ok(**kwargs))
        # 设置JWT cookie
        set_access_cookies(resp, access_token, max_age=max_age)
        return resp

    @classmethod
    def logout_success(cls, **kwargs):
        """
        返回登出成功响应，自动清除JWT cookie
        
        Args:
            **kwargs: 其他响应数据
            
        Returns:
            flask.Response: 已清除JWT cookie的Flask响应对象
        """
        resp = make_response(cls.ok(**kwargs))
        # 清除JWT cookie
        unset_jwt_cookies(resp)
        return resp

    @classmethod
    def fail(cls, message='error', **kwargs):
        """
        返回失败响应（状态码400）
        
        Args:
            message (str): 响应消息
            **kwargs: 其他响应数据
            
        Returns:
            flask.Response: Flask JSON响应对象
        """
        return cls(code=400, message=message, **kwargs).to_json()

    @classmethod
    def error(cls, code=400, message='error', **kwargs):
        """
        返回错误响应（自定义状态码）
        
        Args:
            code (int): 错误状态码
            message (str): 错误消息
            **kwargs: 其他响应数据
            
        Returns:
            flask.Response: Flask JSON响应对象
        """
        return cls(code=code, message=message, **kwargs).to_json()

    @classmethod
    def not_authorized(cls, message='Unauthorized', **kwargs):
        """
        返回未授权响应（状态码401）
        
        Args:
            message (str): 响应消息
            **kwargs: 其他响应数据
            
        Returns:
            flask.Response: Flask JSON响应对象
        """
        return cls(code=401, message=message, **kwargs).to_json()

    @classmethod
    def forbidden(cls, message='Forbidden', **kwargs):
        """
        返回禁止访问响应（状态码403）
        
        Args:
            message (str): 响应消息
            **kwargs: 其他响应数据
            
        Returns:
            flask.Response: Flask JSON响应对象
        """
        return cls(code=403, message=message, **kwargs).to_json()

    @classmethod
    def not_found(cls, message='Not Found', **kwargs):
        """
        返回资源未找到响应（状态码404）
        
        Args:
            message (str): 响应消息
            **kwargs: 其他响应数据
            
        Returns:
            flask.Response: Flask JSON响应对象
        """
        return cls(code=404, message=message, **kwargs).to_json()

    @classmethod
    def internal_error(cls, message='Internal Server Error', **kwargs):
        """
        返回服务器内部错误响应（状态码500）
        
        Args:
            message (str): 响应消息
            **kwargs: 其他响应数据
            
        Returns:
            flask.Response: Flask JSON响应对象
        """
        return cls(code=500, message=message, **kwargs).to_json()

    @staticmethod
    def send_attachment_file(file, mimetype=None):
        """
        发送文件作为附件响应
        Args:
            file (str): 文件路径或文件对象
            mimetype (str): 文件的MIME类型
        Returns:
            flask.Response: 以附件形式发送的文件响应
        """
        return send_file(file, mimetype=mimetype, as_attachment=True)
