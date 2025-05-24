from app_backend import db
from sqlalchemy.dialects.mysql import VARCHAR

class Competition_model(db.Model):
    __tablename__ = 'competition'
    id = db.Column(db.Integer, primary_key=True)
    # cname = db.Column(db.String(30), nullable=False)
    cname = db.Column(VARCHAR(50, charset='utf8mb4'), nullable=False)
    user_id = db.Column(db.String(36), nullable=False)

    def save(self):
        db.session.add(self)
        db.session.commit()



