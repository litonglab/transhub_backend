from app_backend import db


class graph_model(db.Model):
    __tablename__ = 'graph'
    task_id = db.Column(db.String(36), primary_key=False)
    # user_id = db.Column(db.String(36), primary_key=False)
    graph_id = db.Column(db.String(36), primary_key=True)
    graph_type = db.Column(db.String(20)) # throughput, delay
    graph_path = db.Column(db.String(255))

    def update(self, **kwargs):
        try:
            with db.session.begin_nested():
                for key, value in kwargs.items():
                    setattr(self, key, value)
                db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e

    def insert(self):
        db.session.add(self)
        db.session.commit()

