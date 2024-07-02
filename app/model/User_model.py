from app.config import USER_DIR_PATH, ALL_CLASS
from app.extensions import db


class User_model(db.Model):
    __tablename__ = 'student'
    user_id = db.Column(db.String(36), primary_key=True)
    username = db.Column(db.String(30), nullable=False)
    password = db.Column(db.String(30), nullable=False)
    real_name = db.Column(db.String(50), nullable=False)
    sno = db.Column(db.String(11), nullable=False)

    def save(self):
        db.session.add(self)
        db.session.commit()

    def get_user_dir(self, cname):
        return USER_DIR_PATH + "/" + self.username + "_" + self.sno + "/" + ALL_CLASS[cname]

    def is_exist(self) -> bool:
        # user_name is unique, sno is unique
        user = User_model.query.filter_by(username=self.username).first()
        if user:
            return True
        user = User_model.query.filter_by(sno=self.sno).first()
        if user:
            return True
        return False

    def is_null_info(self):
        if self.real_name == '' or self.sno == '' or self.real_name == '' or self.sno == '':
            return True
        else:
            return False

    def update_real_info(self, real_name, sno):
        self.real_name = real_name
        self.sno = sno
        db.session.commit()
