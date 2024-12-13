from app_backend import db


class Competition_model(db.Model):
    __tablename__ = 'competition'
    id = db.Column(db.Integer, primary_key=True)
    cname = db.Column(db.String(30), nullable=False)
    user_id = db.Column(db.String(36), nullable=False)

    def save(self):
        db.session.add(self)
        db.session.commit()



