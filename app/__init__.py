from flask import Flask
from flask_login import LoginManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from config import Config

app = Flask(__name__)
app.config.from_object(Config)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message_category = 'danger'
limiter = Limiter(app, key_func=get_remote_address)

from app import views
