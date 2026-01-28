# Transhub Backend Configuration Guide

本指南介绍如何配置 Transhub Backend 的开发环境和生产环境。

## 概述

Transhub Backend 现在使用基于环境的配置管理系统，支持：
- 开发环境 (development)
- 生产环境 (production)  
- 测试环境 (testing)

配置系统遵循 [12-factor app](https://12factor.net/) 原则，使用环境变量管理敏感信息。

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 创建环境配置文件

使用配置管理脚本创建环境文件：

```bash
# 创建开发环境配置
python manage_config.py create --env development

# 创建生产环境配置
python manage_config.py create --env production
```

### 3. 编辑配置文件

编辑生成的 `.env.development` 或 `.env.production` 文件，更新以下配置：

- 数据库连接信息
- Redis 连接信息
- 基础目录路径
- CORS 允许的域名（生产环境）

### 4. 验证配置

```bash
# 验证开发环境配置
python manage_config.py validate --env development

# 验证生产环境配置
python manage_config.py validate --env production
```

### 5. 启动应用

```bash
# 设置环境变量
export APP_ENV=development  # 或 production

# 启动应用
python run.py
```

## 配置文件结构

```
app_backend/
├── config/
│   ├── __init__.py          # 配置模块入口
│   ├── base.py              # 基础配置类
│   ├── development.py       # 开发环境配置
│   ├── production.py        # 生产环境配置
│   └── testing.py           # 测试环境配置
├── .env.example             # 环境变量模板
├── .env.development         # 开发环境变量（需创建）
├── .env.production          # 生产环境变量（需创建）
└── manage_config.py         # 配置管理脚本
```

## 环境变量说明

### 应用设置
- `APP_NAME`: 应用名称
- `APP_ENV`: 环境类型 (development/production/testing)
- `DEBUG`: 调试模式 (true/false)
- `TESTING`: 测试模式 (true/false)

### 安全设置
- `SECRET_KEY`: Flask 密钥（自动生成）
- `JWT_SECRET_KEY`: JWT 密钥（自动生成）
- `JWT_ACCESS_TOKEN_EXPIRES`: JWT 令牌过期时间（秒）

### 数据库设置
- `MYSQL_USERNAME`: MySQL 用户名
- `MYSQL_PASSWORD`: MySQL 密码
- `MYSQL_ADDRESS`: MySQL 地址 (host:port)
- `MYSQL_DBNAME`: 数据库名称

### Redis 设置
- `REDIS_HOST`: Redis 主机
- `REDIS_PORT`: Redis 端口
- `REDIS_DB`: Redis 数据库编号
- `REDIS_PASSWORD`: Redis 密码（可选）

### 目录设置
- `BASEDIR`: 应用数据基础目录

### 日志设置
- `LOG_LEVEL`: 日志级别 (DEBUG/INFO/WARNING/ERROR)
- `LOG_MAX_BYTES`: 单个日志文件最大大小
- `LOG_BACKUP_COUNT`: 保留的日志文件数量
- `LOG_FILENAME`: 日志文件名

### 服务器设置
- `GUNICORN_ADDRESS`: Gunicorn 监听地址
- `GUNICORN_WORKERS`: Gunicorn 工作进程数
- `GUNICORN_THREADS`: 每个进程的线程数

### 任务队列设置
- `DRAMATIQ_PROCESSES`: Dramatiq 工作进程数
- `DRAMATIQ_THREADS`: 每个进程的线程数

### CORS 设置
- `CORS_ORIGINS`: 允许的跨域源（用逗号分隔）

## 环境特定配置

### 开发环境 (development)
- 启用调试模式
- 详细日志输出 (DEBUG 级别)
- 较少的工作进程
- 允许所有 CORS 源

### 生产环境 (production)
- 禁用调试模式
- 标准日志输出 (INFO 级别)
- 更多工作进程
- 限制 CORS 源
- 更大的日志文件和更多备份

### 测试环境 (testing)
- 启用测试模式
- 使用临时目录
- 使用独立的 Redis 数据库
- 最少的工作进程

## 配置管理命令

### 创建配置文件
```bash
python manage_config.py create --env development
python manage_config.py create --env production
```

### 验证配置
```bash
python manage_config.py validate --env development
python manage_config.py validate --env production
```

### 查看配置
```bash
python manage_config.py show --env development
python manage_config.py show --env production
```

### 生成密钥
```bash
python manage_config.py generate-key
```

## 迁移指南

### 从旧配置系统迁移

1. 备份现有的 `app_backend/config.py` 文件
2. 运行配置创建命令生成新的环境文件
3. 将旧配置中的值复制到新的环境文件中
4. 验证新配置是否正常工作
5. 更新部署脚本以设置 `APP_ENV` 环境变量

### 向后兼容性

新的配置系统保持与旧系统的向后兼容性：
- 旧的配置导入仍然有效（会显示弃用警告）
- 现有的配置字典（如 `MYSQL_CONFIG`）仍然可用
- 逐步迁移到新系统

## 安全最佳实践

1. **永远不要提交敏感配置文件到版本控制**
   - `.env.development` 和 `.env.production` 已添加到 `.gitignore`

2. **在生产环境中使用强密码**
   - 数据库密码
   - Redis 密码（如果启用）
   - 自动生成的密钥已经足够安全

3. **限制 CORS 源**
   - 生产环境中不要使用 `*`
   - 明确指定允许的域名

4. **定期轮换密钥**
   - 定期更新 `SECRET_KEY` 和 `JWT_SECRET_KEY`

5. **使用环境变量覆盖**
   - 在容器化部署中使用环境变量而不是文件

## 故障排除

### 配置验证失败
1. 检查环境文件是否存在
2. 验证环境变量格式
3. 确保必需的服务（MySQL、Redis）正在运行

### 导入错误
1. 确保安装了所有依赖：`pip install -r requirements.txt`
2. 检查 `APP_ENV` 环境变量是否正确设置

### 数据库连接失败
1. 验证数据库配置
2. 确保数据库服务正在运行
3. 检查网络连接和防火墙设置

### Redis 连接失败
1. 验证 Redis 配置
2. 确保 Redis 服务正在运行
3. 检查密码设置（如果启用）

## 支持

如果遇到配置问题，请：
1. 查看应用日志
2. 运行配置验证命令
3. 检查环境变量设置
4. 参考本文档的故障排除部分
