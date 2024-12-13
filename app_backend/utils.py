import redis
import socket
import threading

# 配置Redis客户端
redis_client = redis.Redis(host='localhost', port=6379, db=0)

# 用于管理分配的端口
allocated_ports = set()


def path_remake(path):
    return path.replace(' ', '\ ').replace('(', '\(').replace(')', '\)').replace('&', '\&')


def acquire_redis_lock(port):
    lock_name = f"port_lock_{port}"
    return redis_client.set(lock_name, "locked", nx=True, ex=600)  # 设置过期时间为60秒


def release_redis_lock(port):
    lock_name = f"port_lock_{port}"
    redis_client.delete(lock_name)


def get_available_port():
    port = 50000
    maxport = 65535
    while port <= maxport:
        if acquire_redis_lock(port):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(("", port))
                    s.close()  # 释放端口
                    allocated_ports.add(port)
                    return port
                except OSError:
                    release_redis_lock(port)
                    port += 1
        else:
            port += 1
    raise Exception("No available port")


def release_port(port):
    with threading.Lock():
        if port in allocated_ports:
            allocated_ports.remove(port)
            release_redis_lock(port)
