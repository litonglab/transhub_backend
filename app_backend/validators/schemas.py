"""
Pydantic schemas for API request validation.
"""
import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app_backend.config import cname_list


class UserLoginSchema(BaseModel):
    """用户登录请求参数验证"""
    username: str = Field(..., min_length=4, max_length=16, description="用户名，4-16个字符")
    password: str = Field(..., min_length=6, max_length=18, description="密码，6-18个字符")
    cname: str = Field(..., description="比赛名称")

    @field_validator('username')
    def validate_username(cls, v):
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError('用户名只能包含字母、数字和下划线')
        return v

    @field_validator('password')
    def validate_password(cls, v):
        if not re.match(r'^[a-zA-Z0-9!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?]+$', v):
            raise ValueError('密码包含非法字符')
        return v

    @field_validator('cname')
    def validate_cname(cls, v):
        if v not in cname_list:
            raise ValueError(f'比赛名称必须是以下之一: {", ".join(cname_list)}')
        return v


class UserRegisterSchema(BaseModel):
    """用户注册请求参数验证"""
    username: str = Field(..., min_length=4, max_length=16, description="用户名，4-16个字符")
    password: str = Field(..., min_length=6, max_length=18, description="密码，6-18个字符")
    real_name: str = Field(..., min_length=1, max_length=50, description="真实姓名")
    sno: str = Field(..., min_length=10, max_length=10, description="学号，10位数字")

    @field_validator('username')
    def validate_username(cls, v):
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError('用户名只能包含字母、数字和下划线')
        return v

    @field_validator('password')
    def validate_password(cls, v):
        if not re.match(r'^[a-zA-Z0-9!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?]+$', v):
            raise ValueError('密码包含非法字符')
        return v

    @field_validator('real_name')
    def validate_real_name(cls, v):
        if not v.strip():
            raise ValueError('真实姓名不能为空')
        return v.strip()

    @field_validator('sno')
    def validate_sno(cls, v):
        if not v.isdecimal():
            raise ValueError('学号必须是10位数字')
        if len(v) != 10:
            raise ValueError('学号必须是10位数字')
        # 读取student_list.txt文件，文件每行是一个学号，表示允许注册的学号，如果学号不在列表中，则抛出异常
        with open('app_backend/validators/student_list.txt', 'r') as f:
            allowed_snos = {line.strip() for line in f if line.strip()}
        if len(allowed_snos) > 0 and v not in allowed_snos:
            raise ValueError('该学号不在允许注册的列表中')
        return v


class ChangePasswordSchema(BaseModel):
    """修改密码请求参数验证"""
    user_id: str = Field(..., description="用户ID")
    oldpwd: str = Field(..., min_length=6, max_length=18, description="旧密码")
    new_pwd: str = Field(..., min_length=6, max_length=18, description="新密码，6-18个字符")

    @field_validator('user_id')
    def validate_user_id(cls, v):
        if not v.strip():
            raise ValueError('用户ID不能为空')
        return v.strip()

    @field_validator('new_pwd')
    def validate_new_password(cls, v):
        if not re.match(r'^[a-zA-Z0-9!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?]+$', v):
            raise ValueError('新密码包含非法字符')
        return v


class TaskInfoSchema(BaseModel):
    """获取任务信息请求参数验证"""
    task_id: str = Field(..., description="任务ID")

    @field_validator('task_id')
    def validate_task_id(cls, v):
        if not v.strip():
            raise ValueError('任务ID不能为空')
        return v.strip()


class HistoryDetailSchema(BaseModel):
    """获取历史记录详情请求参数验证"""
    upload_id: str = Field(..., description="上传ID")

    @field_validator('upload_id')
    def validate_upload_id(cls, v):
        if not v.strip():
            raise ValueError('上传ID不能为空')
        return v.strip()


class SummaryRanksSchema(BaseModel):
    """获取排行榜请求参数验证"""
    cname: Optional[str] = Field(None, description="比赛名称")


class SourceCodeSchema(BaseModel):
    """获取源码请求参数验证"""
    upload_id: str = Field(..., description="上传ID")

    @field_validator('upload_id')
    def validate_upload_id(cls, v):
        if not v.strip():
            raise ValueError('上传ID不能为空')
        return v.strip()


class GraphSchema(BaseModel):
    """获取图表请求参数验证"""
    task_id: str = Field(..., description="任务ID")
    graph_type: str = Field(..., description="图表类型")

    @field_validator('task_id')
    def validate_task_id(cls, v):
        if not v.strip():
            raise ValueError('任务ID不能为空')
        return v.strip()

    @field_validator('graph_type')
    def validate_graph_type(cls, v):
        allowed_types = ['throughput', 'delay']
        if v not in allowed_types:
            raise ValueError(f'图表类型必须是以下之一: {", ".join(allowed_types)}')
        return v
