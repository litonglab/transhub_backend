from app import create_app

# from concurrent.futures import ThreadPoolExecutor

# from app.extensions import rq


# def begin_work():
#     worker = rq.get_worker()
#     worker.work()


app = create_app()
# executor = ThreadPoolExecutor(8)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=54321, debug=False)

# scheduler = rq.get_scheduler(interval=5)
# scheduler.run()
# executor.submit(begin_work)
