"""
Pydantic schemas for API request validation.
"""
import logging
import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app_backend import get_default_config

logger = logging.getLogger(__name__)
config = get_default_config()


class FieldRules:
    """字段验证规则常量"""
    USERNAME_MIN_LEN = 4
    USERNAME_MAX_LEN = 16
    PASSWORD_MIN_LEN = 6
    PASSWORD_MAX_LEN = 18
    REAL_NAME_MIN_LEN = 1
    REAL_NAME_MAX_LEN = 50
    STUDENT_ID_LEN = 10


class CommonValidators:
    """公共验证器类，包含可重用的验证函数"""

    @staticmethod
    def validate_username(v: str) -> str:
        """验证用户名格式
        规则：
        1. 支持中文、字母、数字和下划线
        2. 不能包含文件系统特殊字符
        3. 不能以点号开头（避免隐藏文件）
        4. 不能包含连续的点号（避免目录遍历）
        """
        logger.debug(f"Validating username: {v}")

        # 检查是否为空
        v = CommonValidators.validate_not_empty(v, "用户名")

        # 检查是否以点号开头
        if v.startswith('.'):
            logger.warning(f"Username starts with dot: {v}")
            raise ValueError('用户名不能以点号开头')

        # 检查是否包含连续的点号
        if '..' in v:
            logger.warning(f"Username contains consecutive dots: {v}")
            raise ValueError('用户名不能包含连续的点号')

        # 检查是否包含文件系统特殊字符
        invalid_chars = r'[<>:"/\\|?*]'
        if re.search(invalid_chars, v):
            logger.warning(f"Username contains invalid characters: {v}")
            raise ValueError('用户名不能包含特殊字符: < > : " / \\ | ? *')

        # 检查是否只包含有效字符（中文、字母、数字、下划线、点号）
        if not re.match(r'^[\u4e00-\u9fa5a-zA-Z0-9_.]+$', v):
            logger.warning(f"Username contains invalid characters: {v}")
            raise ValueError('用户名只能包含中文、字母、数字、下划线和点号')

        return v

    @staticmethod
    def validate_password(v: str) -> str:
        """验证密码格式"""
        logger.debug("Validating password")
        if not re.match(r'^[a-zA-Z0-9!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?]+$', v):
            logger.warning("Invalid password format")
            raise ValueError('密码包含非法字符')
        return v

    @staticmethod
    def validate_real_name(v: str) -> str:
        """验证真实姓名"""
        logger.debug(f"Validating real name: {v}")
        if not v.strip():
            logger.warning("Empty real name")
            raise ValueError('真实姓名不能为空')
        return v.strip()

    @staticmethod
    def validate_not_empty(v: str, field_name: str) -> str:
        """验证字段不能为空"""
        logger.debug(f"Validating {field_name}: {v} is empty or not.")
        if not v.strip():
            logger.warning(f"{field_name} is empty, validation failed.")
            raise ValueError(f'{field_name}不能为空')
        return v.strip()


class UserLoginSchema(BaseModel):
    """用户登录请求参数验证"""
    username: str = Field(..., min_length=FieldRules.USERNAME_MIN_LEN, max_length=FieldRules.USERNAME_MAX_LEN,
                          description=f"用户名，{FieldRules.USERNAME_MIN_LEN}-{FieldRules.USERNAME_MAX_LEN}个字符")
    password: str = Field(..., min_length=FieldRules.PASSWORD_MIN_LEN, max_length=FieldRules.PASSWORD_MAX_LEN,
                          description=f"密码，{FieldRules.PASSWORD_MIN_LEN}-{FieldRules.PASSWORD_MAX_LEN}个字符")
    cname: str = Field(..., description="比赛名称")

    @field_validator('username')
    def validate_username(cls, v):
        return CommonValidators.validate_username(v)

    @field_validator('password')
    def validate_password(cls, v):
        return CommonValidators.validate_password(v)

    @field_validator('cname')
    def validate_cname(cls, v):
        logger.debug(f"Validating competition name: {v}")
        if v not in config.Course.CNAME_LIST:
            logger.warning(f"Invalid competition name: {v}")
            raise ValueError(f'比赛名称必须是以下之一: {", ".join(config.Course.CNAME_LIST)}')
        _config = config.get_course_config(v)
        if _config['allow_login'] is False:
            logger.warning(f"Competition {v} login not allowed")
            raise ValueError(f'{v}：此课程（比赛）暂未开放登录')
        return v


class UserRegisterSchema(BaseModel):
    """用户注册请求参数验证"""
    username: str = Field(..., min_length=FieldRules.USERNAME_MIN_LEN, max_length=FieldRules.USERNAME_MAX_LEN,
                          description=f"用户名，{FieldRules.USERNAME_MIN_LEN}-{FieldRules.USERNAME_MAX_LEN}个字符")
    password: str = Field(..., min_length=FieldRules.PASSWORD_MIN_LEN, max_length=FieldRules.PASSWORD_MAX_LEN,
                          description=f"密码，{FieldRules.PASSWORD_MIN_LEN}-{FieldRules.PASSWORD_MAX_LEN}个字符")
    real_name: str = Field(..., min_length=FieldRules.REAL_NAME_MIN_LEN, max_length=FieldRules.REAL_NAME_MAX_LEN,
                           description=f"真实姓名，{FieldRules.REAL_NAME_MIN_LEN}-{FieldRules.REAL_NAME_MAX_LEN}个字符")
    sno: str = Field(..., min_length=FieldRules.STUDENT_ID_LEN, max_length=FieldRules.STUDENT_ID_LEN,
                     description=f"学号，{FieldRules.STUDENT_ID_LEN}位数字")

    @field_validator('username')
    def validate_username(cls, v):
        return CommonValidators.validate_username(v)

    @field_validator('password')
    def validate_password(cls, v):
        return CommonValidators.validate_password(v)

    @field_validator('real_name')
    def validate_real_name(cls, v):
        return CommonValidators.validate_real_name(v)

    @field_validator('sno')
    def validate_sno(cls, v):
        logger.debug(f"Validating student number: {v}")
        if not v.isdecimal():
            logger.warning(f"Invalid student number format: {v}")
            raise ValueError('学号必须是10位数字')
        if len(v) != FieldRules.STUDENT_ID_LEN:
            logger.warning(f"Invalid student number length: {len(v)}")
            raise ValueError(f'学号必须是{FieldRules.STUDENT_ID_LEN}位数字')
        if len(config.Course.REGISTER_STUDENT_LIST) > 0 and v not in config.Course.REGISTER_STUDENT_LIST:
            logger.warning(f"Student number {v} not in allowed list")
            raise ValueError('该学号不在允许注册的名单中，请确认你已选课或报名竞赛。')
        return v


class ChangePasswordSchema(BaseModel):
    """修改密码请求参数验证"""
    old_pwd: str = Field(..., min_length=FieldRules.PASSWORD_MIN_LEN, max_length=FieldRules.PASSWORD_MAX_LEN,
                         description=f"旧密码，{FieldRules.PASSWORD_MIN_LEN}-{FieldRules.PASSWORD_MAX_LEN}个字符")
    new_pwd: str = Field(..., min_length=FieldRules.PASSWORD_MIN_LEN, max_length=FieldRules.PASSWORD_MAX_LEN,
                         description=f"新密码，{FieldRules.PASSWORD_MIN_LEN}-{FieldRules.PASSWORD_MAX_LEN}个字符")

    @field_validator('old_pwd')
    def validate_old_password(cls, v):
        return CommonValidators.validate_password(v)

    @field_validator('new_pwd')
    def validate_new_password(cls, v):
        return CommonValidators.validate_password(v)


class UserChangeRealInfoSchema(BaseModel):
    """用户信息修改请求参数验证"""
    real_name: str = Field(..., min_length=FieldRules.REAL_NAME_MIN_LEN, max_length=FieldRules.REAL_NAME_MAX_LEN,
                           description=f"真实姓名，{FieldRules.REAL_NAME_MIN_LEN}-{FieldRules.REAL_NAME_MAX_LEN}个字符")

    @field_validator('real_name')
    def validate_real_name(cls, v):
        return CommonValidators.validate_real_name(v)


class HistoryDetailSchema(BaseModel):
    """获取历史记录详情请求参数验证"""
    upload_id: str = Field(..., description="上传ID")

    @field_validator('upload_id')
    def validate_upload_id(cls, v):
        return CommonValidators.validate_not_empty(v, "upload_id")


class SummaryRanksSchema(BaseModel):
    """获取排行榜请求参数验证"""
    cname: str = Field(..., description="比赛名称")

    @field_validator('cname')
    def validate_cname(cls, v):
        return CommonValidators.validate_not_empty(v, "比赛名称")


class SourceCodeSchema(BaseModel):
    """获取源码请求参数验证"""
    upload_id: str = Field(..., description="上传ID")

    @field_validator('upload_id')
    def validate_upload_id(cls, v):
        return CommonValidators.validate_not_empty(v, "upload_id")


class GraphSchema(BaseModel):
    """获取图表请求参数验证"""
    task_id: str = Field(..., description="任务ID")
    graph_type: str = Field(..., description="图表类型")

    @field_validator('task_id')
    def validate_task_id(cls, v):
        return CommonValidators.validate_not_empty(v, "task_id")

    @field_validator('graph_type')
    def validate_graph_type(cls, v):
        logger.debug(f"Validating graph type: {v}")
        allowed_types = ['throughput', 'delay']
        if v not in allowed_types:
            logger.warning(f"Invalid graph type: {v}")
            raise ValueError(f'图表类型必须是以下之一: {", ".join(allowed_types)}')
        return v


class FileUploadSchema(BaseModel):
    """文件上传请求参数验证"""
    file: Optional[object] = Field(None, description="上传的文件")

    class Config:
        # 允许任意类型，因为我们需要处理FileStorage对象
        arbitrary_types_allowed = True

    @field_validator('file')
    def validate_file(cls, file):
        """验证上传的文件"""
        logger.debug("Starting file validation")
        if not file:
            logger.warning("No file received")
            raise ValueError("未接收到文件")

        if not hasattr(file, 'filename') or not file.filename:
            logger.warning("Empty filename")
            raise ValueError("文件名为空")

        filename = file.filename
        logger.debug(f"Validating file: {filename}")

        # 验证文件后缀名
        allowed_extensions = ['.c', '.cc', '.cpp']
        file_extension = None
        for ext in allowed_extensions:
            if filename.lower().endswith(ext):
                file_extension = ext
                break

        if not file_extension:
            logger.warning(f"Invalid file extension: {filename}")
            raise ValueError("文件必须是C程序(.c)或C++程序(.cc, .cpp)")

        # 验证文件名格式（只允许字母、数字、下划线、点号）
        if not re.match(r'^[a-zA-Z0-9_.-]+$', filename):
            logger.warning(f"Invalid filename format: {filename}")
            raise ValueError("文件名只能包含字母、数字、下划线、点号和连字符")

        # 验证文件大小（例如限制为2MB）
        max_size = 2 * 1024 * 1024  # 2MB
        if hasattr(file, 'content_length') and file.content_length:
            if file.content_length > max_size:
                logger.warning(f"File too large: {file.content_length} bytes")
                raise ValueError(f"文件大小不能超过{max_size // (1024 * 1024)}MB")

        # 如果文件有stream属性，检查实际内容大小
        if hasattr(file, 'stream'):
            current_pos = file.stream.tell()
            file.stream.seek(0, 2)  # 移动到文件末尾
            file_size = file.stream.tell()
            file.stream.seek(current_pos)  # 恢复原位置

            if file_size > max_size:
                logger.warning(f"File stream too large: {file_size} bytes")
                raise ValueError(f"文件大小不能超过{max_size // (1024 * 1024)}MB")

            if file_size == 0:
                logger.warning("Empty file content")
                raise ValueError("文件内容为空")

        # 验证文件内容安全性
        logger.debug("Validating file content safety")
        cls._validate_file_content_safety(file)
        logger.info(f"File validation successful: {filename}")

        return file

    @classmethod
    def _validate_file_content_safety(cls, file):
        """
        验证文件内容安全性
        检查是否包含危险函数调用
        """
        logger.debug("Starting file content safety validation")
        dangerous_functions = [
            # 文件系统操作
            "fopen", "open", "creat", "remove", "unlink", "rename",
            "mkdir", "rmdir", "chmod", "chown", "symlink", "link",
            # 进程/系统命令
            "system", "execve", "execv", "execl", "execle", "execlp",
            "execvp", "execvpe", "popen", "fork", "vfork",
            # 动态代码加载
            "dlopen", "dlsym", "dlclose", "dlerror",
            # 网络操作
            "socket", "connect", "bind", "listen", "accept",
            "send", "sendto", "recv", "recvfrom",
            # 内存/指针操作 (可能用于漏洞利用)
            # "gets", "strcpy", "strcat", "sprintf", "vsprintf",
            # "scanf", "sscanf",
            # "malloc", "free",  # 需结合上下文分析
            # 系统资源操作
            "ioctl", "syscall",  # 直接系统调用
            "mmap", "munmap", "mprotect",  # 内存映射
            # 环境/权限相关
            "setuid", "setgid", "seteuid", "setegid",
            "putenv", "clearenv", "getenv",
            # 信号处理 (可能干扰沙箱)
            "signal", "sigaction", "raise",
            # Windows API (如果跨平台需检测)
            "WinExec", "CreateProcess", "ShellExecute",
            # 多线程相关
            "pthread_create",
            # 其他危险函数
            "abort", "exit", "_exit"  # 可能用于强制终止监控进程
        ]

        try:
            # 保存当前位置
            current_pos = file.stream.tell()
            file.stream.seek(0)

            # 读取文件内容
            code = file.stream.read().decode(errors='ignore')

            # 恢复文件流位置
            file.stream.seek(current_pos)

            # 检查危险函数
            for func in dangerous_functions:
                if re.search(rf'\b{func}\s*\(', code):
                    raise ValueError(f"文件包含危险函数调用: {func}")

        except UnicodeDecodeError:
            logger.warning("File content cannot be decoded, possibly not a valid text file")
            raise ValueError("文件内容无法解码，可能不是有效的文本文件")
        except Exception as e:
            if "危险函数调用" in str(e):
                logger.warning(f"Dangerous function call found in file: {str(e)}")
                raise e  # 重新抛出危险函数错误
            logger.warning(f"File content check failed: {str(e)}")
            raise ValueError(f"文件内容检查失败: {str(e)}")
