from app import create_app

flask_app = create_app()

if __name__ == "__main__":
    import redis
    from rq import Connection, Worker

    redis_conn = redis.from_url(flask_app.settings.redis_url)
    with flask_app.app_context():
        with Connection(redis_conn):
            worker = Worker(["summaries"])
            worker.work()
