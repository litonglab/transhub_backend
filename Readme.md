# Transhub Backend

本仓库是Transhub的后端代码仓库，使用Flask框架开发，用flask rq实现任务队列及多进程  
前端链接：[Transhub Frontend](https://github.com/litonglab/transhub_frontend)

## 1. 部署

- 依赖软件：Mysql，Redis，Linux，Python 3.8+
- 安装python依赖

```shell
pip install -r requirements.txt
```

pip install python-dotenv

- 修改app/config
    - 将`BASEDIR`修改成你想要的目录，并且修改数据库配置
    - 项目中提供了`pantheon-network`,你可以直接将它复制到`BSAEDIR`下
    - 配置你的mysql数据库,需要先创建数据库，不需要创建表，项目会自动创建
    - 配置你的redis数据库
- 设置环境变量

```shell
#vim ~/.bashrc
FLASK_APP = run.py
FLASK_ENV = development
FLASK_DEBUG = 0
```

- 以开发模式启动
    - 启动flask
      ```shell
        python3 -m flask run
      ```
    - 启动rq worker  
      在当前目录下新建shell
      ```shell
        rq worker
      ```

- 以生产模式启动

```shell
bash ./start.sh
# bash ./stop.sh
```
