# Transhub Backend

本仓库是Transhub的后端代码仓库，使用Flask框架开发，用Dramatiq实现任务队列及多进程处理。
前端链接：[Transhub Frontend](https://github.com/litonglab/transhub_frontend)

## 🚀 快速开始

### 1. 系统要求

- **Python**: 3.8+
- **数据库**: MySQL 5.7+ 或 MariaDB 10.3+
- **缓存**: Redis 5.0+
- **操作系统**: Linux

### 2. 安装依赖

```bash
# 克隆项目
git clone <repository-url>
cd transhub_backend

# 安装Python依赖
pip install -r requirements.txt
```

### 3. 系统配置
#### 环境配置

```bash
# 复制模板文件（开发环境）
cp .env.example .env.development

# 编辑配置文件
vim .env.development
```

#### 课程配置

将`app_backend/config/config_example.py`复制为`development.py` （开发环境）或 `production.py` （生产环境），复制文件后，需要修改类名为对应的`DevelopmentConfig`和`ProductionConfig`，并根据需要修改配置。

### 4. 配置数据库和Redis

编辑环境配置文件，更新以下配置：

```bash
# 数据库配置
MYSQL_USERNAME=root
MYSQL_PASSWORD=your_password
MYSQL_ADDRESS=localhost:3306
MYSQL_DBNAME=transhub_dev

# Redis配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=1

# 基础目录
BASEDIR=/path/to/your/transhub/data
```

### 5. 启动应用

#### 开发环境

```bash
python run.py
```

#### 生产环境

```bash
# 使用 Supervisor 管理（推荐）
bash supervisor_manager.sh start
```

## 📁 项目结构

```
transhub_backend/
├── app_backend/                 # 应用主目录
│   ├── config/                  # 配置模块
│   │   ├── __init__.py         # 配置入口
│   │   ├── base.py             # 基础配置
│   │   ├── development.py      # 开发环境配置
│   │   ├── production.py       # 生产环境配置
│   │   └── testing.py          # 测试环境配置
│   ├── views/                   # 视图模块
│   ├── model/                   # 数据模型
│   ├── jobs/                    # 后台任务
│   ├── utils/                   # 工具函数
│   └── ...
├── .env.example                 # 环境变量模板
├── .env.development            # 开发环境配置（需创建）
├── .env.production             # 生产环境配置（需创建）
├── manage_config.py            # 配置管理脚本
├── start.py                    # 启动脚本
├── run.py                      # 应用入口
├── supervisor.ini              # Supervisor配置
├── supervisor_manager.sh       # Supervisor管理脚本
└── requirements.txt            # Python依赖
```

## ⚙️ 配置说明

### 环境变量配置

项目支持两种环境：

- **development**: 开发环境，启用调试模式，详细日志
- **production**: 生产环境，优化性能，安全配置

### 嵌套类配置结构

配置文件使用嵌套类来组织不同模块的配置，便于管理：

```python
class DevelopmentConfig:
    class App:          # 应用基础配置
    class Database:     # 数据库配置
    class Cache:        # 缓存配置
    class Security:     # 安全配置
    class Logging:      # 日志配置
    class Server:       # 服务器配置
    class TaskQueue:    # 任务队列配置
    class Course:       # 课程配置
```

可以通过嵌套类访问配置：
```python
config = get_config('development')
debug_mode = config.App.DEBUG
mysql_user = config.Database.MYSQL_USERNAME
redis_host = config.Cache.REDIS_HOST
```

### 主要配置项

| 配置项 | 说明 | 开发环境默认值 | 生产环境建议值 |
|--------|------|----------------|----------------|
| `APP_ENV` | 环境名称 | development | production |
| `DEBUG` | 调试模式 | true | false |
| `BASEDIR` | 数据目录 | ./project/Transhub_data_dev | /path/to/your/transhub/data |
| `MYSQL_DBNAME` | 数据库名 | transhub_dev | transhub_prod |
| `REDIS_DB` | Redis数据库 | 0 | 0 |
| `LOG_LEVEL` | 日志级别 | DEBUG | INFO |



## 🚀 部署方式

### 开发环境部署

```bash
# 1. 创建开发环境配置
cp .env.example .env.development

# 2. 编辑配置文件
vim .env.development

# 3. 启动开发服务器
# 启动Flask
python run.py
# 任务队列
dramatiq app_backend.jobs.cctraining_job --processes 2 --threads 2 --queues cc_training   （评测任务）
dramatiq app_backend.jobs.graph_job --processes 1 --threads 2 --queues graph  （绘图任务）
```

### 生产环境部署

#### 使用 Supervisor脚本

```bash
# 1. 创建生产环境配置
cp .env.example .env.production

# 2. 编辑配置文件
vim .env.production

# 3. 启动服务
bash supervisor_manager.sh start

# 4. 查看状态
bash supervisor_manager.sh status

# 5. 停止服务
bash supervisor_manager.sh stop
```



## 🔍 监控和日志

### 应用监控

- **应用日志**: `{BASEDIR}/logs/app.log`
- **Supervisor日志**: `{LOG_DIR}/supervisord.log`

### 日志文件位置

```
{BASEDIR}/logs/
├── app.log              # 应用日志
├── flask_app.out.log    # Flask输出日志
├── flask_app.err.log    # Flask错误日志
├── dramatiq.out.log     # Dramatiq输出日志
├── dramatiq.err.log     # Dramatiq错误日志
└── supervisord.log      # Supervisor日志
```

## 🔒 安全最佳实践

1. **生产环境配置**
   - 设置强密码和随机密钥
   - 限制 CORS 来源
   - 使用 HTTPS
   - 定期更新依赖

2. **文件权限**
   
   ```bash
   chmod 600 .env.production  # 限制配置文件权限
   chown app:app -R /var/lib/transhub  # 设置正确的文件所有者
   ```
   
3. **防火墙配置**
   ```bash
   # 只允许必要的端口
   ufw allow 22    # SSH
   ufw allow 80    # HTTP
   ufw allow 443   # HTTPS
   ufw allow 54321 # 应用端口（可选，建议通过反向代理）
   ```

## 🐛 故障排除

### 常见问题

1. **数据库连接失败**
   - 检查数据库服务是否运行
   - 验证连接信息
   - 确保数据库已创建

2. **Redis连接失败**

   - 检查Redis服务状态
   - 验证端口和密码配置

3. **权限问题**

   ```bash
   sudo chown -R $USER:$USER /path/to/transhub_backend
   ```

### 日志查看

```bash
# 查看Supervisor状态
bash supervisor_manager.sh status

# 查看日志
bash supervisor_manager.sh logs
```

## 📚 更多文档及后续开发

- 请参见docs目录下的文档

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

