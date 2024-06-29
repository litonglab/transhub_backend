from app import create_app

from concurrent.futures import ThreadPoolExecutor

from app.extensions import rq


app = create_app()


def begin_work():
    worker = rq.get_worker()
    worker.work()


if __name__ == "__main__":
    executor = ThreadPoolExecutor(8)
    app.run(host="0.0.0.0", port=54321, debug=True)
    app.config['RQ_REDIS_URL'] = 'redis://localhost:6379/0'
    scheduler = rq.get_scheduler(interval=5)
    scheduler.run()
    executor.submit(begin_work)
