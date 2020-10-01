import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

class Config:
    ALLOWED_EXTENSIONS = os.environ.get('ALLOWED_EXTENSIONS') or {'xlsx'}
    API_KEY = os.environ.get('API_KEY') # put your API key from kavenegar here
    CALL_BACK_TOKEN = os.environ.get('CALL BACK TOKEN')
    MAX_FLASH = os.environ.get('MAX_FLASH')
    MYSQL_DB_NAME = os.environ.get('MYSQL_DB_NAME') or 'smsmysql'
    MYSQL_HOST = os.environ.get('MYSQL_HOST') or 'localhost'
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD')
    MYSQL_USERNAME = os.environ.get('MYSQL_USERNAME')
    PASSWORD = os.environ.get('SMS_PASSWORD')
    REMOTE_CALL_API_KEY = os.environ.get('REMOTE_CALL_API_KEY') # 'set_unguessable_remote_api_key_lkjdfljerlj3247LKJ'
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'secret_key' # 'random long string with alphanumeric + #()*&'
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or '/tmp'
    USERNAME = os.environ.get('SMS_USERNAME')
