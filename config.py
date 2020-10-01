import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

class Config:
    ALLOWED_EXTENSIONS = os.environ.get('ALLOWED_EXTENSIONS') or {'xlsx'}
    API_KEY = os.environ.get('API_KEY') # put your API key from kavenegar here
    CALL_BACK_TOKEN = os.environ.get('CALL BACK TOKEN')
    MAX_FLASH = os.environ.get('MAX_FLASH')
    SQLALCHEMY_DATABASE_URI = os.environ.get('SQLALCHEMY_DATABASE_URI')
    SQLALCHEMY_TRACK_MODIFICATIONS = os.environ.get('SQLALCHEMY_TRACK_MODIFICATIONS') or False
    PASSWORD = os.environ.get('SMS_PASSWORD')
    REMOTE_CALL_API_KEY = os.environ.get('REMOTE_CALL_API_KEY') # 'set_unguessable_remote_api_key_lkjdfljerlj3247LKJ'
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'secret_key' # 'random long string with alphanumeric + #()*&'
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or '/tmp'
    USERNAME = os.environ.get('SMS_USERNAME')
