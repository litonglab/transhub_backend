from rq import Queue
from redis import Redis

redis_conn = Redis()
que = Queue(connection=redis_conn)
all_jobs = que.get_jobs()
for job in all_jobs:
    if "simimase" in job.args:
        que.remove(job.id)
        print(f"job_id: {job.id} has been removed from queue, job_args: {job.args}, job_func_name: {job.func_name}")
