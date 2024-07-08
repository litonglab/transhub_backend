from app import db


class History_model(db.Model):
    __tablename__ = 'history'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User_model', back_populates='history')
    date = db.Column(db.DateTime)
    action = db.Column(db.String(255))
    description = db.Column(db.String(255))

    def __init__(self, user_id, date, action, description):
        self.user_id = user_id
        self.date = date
        self.action = action
        self.description = description

    def __repr__(self):
        return '<History %r>' % self.id



