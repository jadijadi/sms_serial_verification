from app import db, login_manager
from flask_login import UserMixin
import enum


class User(UserMixin):
    """ A minimal and singleton user class used
    only for administrative tasks
    """
    def __init__(self, id):
        self.id = id

    def __repr__(self):
        return f"{self.id}"


@login_manager.user_loader
def load_user(userid):
    return User(userid)


class SMSStatusEnum(enum.Enum):
    OK = 'OK'
    FAILURE = 'FAILURE'
    DOUBLE = 'DOUBLE'
    NOT_FOUND = 'NOT-FOUND'

class ProcessedSMS(db.Model):
    __tablename__ = "PROCESSED_SMS"
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.Enum(SMSStatusEnum), index=True, nullable=False)
    sender = db.Column(db.String(20))
    message = db.Column(db.String(400))
    answer = db.Column(db.String(400))
    date = db.Column(db.DateTime, index=True)

class Logs(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    log_name = db.Column(db.String(200))
    log_value = db.Column(db.Text)

class Serials(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ref = db.Column(db.String(200))
    description = db.Column(db.String(200))
    start_serial = db.Column(db.String(30), index=True)
    end_serial = db.Column(db.String(30), index=True)
    date = db.Column(db.DateTime)

class Invalids(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invalid_serial = db.Column(db.String(30), index=True)
