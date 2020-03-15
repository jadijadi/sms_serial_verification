import datetime
import os
import re
import time
import subprocess
from textwrap import dedent

import requests
from flask import (
    Flask,
    Response,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from werkzeug.utils import secure_filename

import config
import MySQLdb
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from pandas import read_excel

app = Flask(__name__)
limiter = Limiter(app, key_func=get_remote_address)

MAX_FLASH = 10
UPLOAD_FOLDER = config.UPLOAD_FOLDER
ALLOWED_EXTENSIONS = config.ALLOWED_EXTENSIONS
CALL_BACK_TOKEN = config.CALL_BACK_TOKEN

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# flask-login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message_category = 'danger'


def allowed_file(filename):
    """ checks the extension of the passed filename to be in the allowed extensions"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


app.config.update(SECRET_KEY=config.SECRET_KEY)


class User(UserMixin):
    """ A minimal and singleton user class used only for administrative tasks """
    def __init__(self, id):
        self.id = id

    def __repr__(self):
        return "%d" % (self.id)


user = User(0)


@app.route('/db_status/', methods=['GET'])
@login_required
def db_status():

    """ show some status about the DB """

    
    db = get_database_connection()
    cur = db.cursor()
    
    # collect some stats for the GUI
    try:
        cur.execute("SELECT count(*) FROM serials")
        num_serials = cur.fetchone()[0]
    except:
        num_serials = 'can not query serials count'

    try:
        cur.execute("SELECT count(*) FROM invalids")
        num_invalids = cur.fetchone()[0]
    except:
        num_invalids = 'can not query invalid count'

    try:
        cur.execute("SELECT log_value FROM logs WHERE log_name = 'import'")
        log_import = cur.fetchone()[0]
    except:
        log_import = 'can not read import log results... yet'

    try:
        cur.execute("SELECT log_value FROM logs WHERE log_name = 'db_filename'")
        log_filename = cur.fetchone()[0]
    except:
        log_filename = 'can not read db filename from database'

    try:
        cur.execute("SELECT log_value FROM logs WHERE log_name = 'db_check'")
        log_db_check = cur.fetchone()[0]
    except:
        log_db_check = 'Can not read db_check logs... yet'

    return render_template('db_status.html', data={'serials': num_serials, 'invalids': num_invalids, 
                                                   'log_import': log_import, 'log_db_check': log_db_check, 'log_filename': log_filename})


@app.route('/', methods=['GET', 'POST'])
@login_required
def home():
    """ creates database if method is post otherwise shows the homepage with some stats
    see import_database_from_excel() for more details on database creation"""
    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part', 'danger')
            return redirect(request.url)
        file = request.files['file']
        # if user does not select file, browser also
        # submit an empty part without filename
        if file.filename == '':
            flash('No selected file', 'danger')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            #TODO: is space find in a file name? check if it works
            filename = secure_filename(file.filename)
            filename.replace(' ', '_') # no space in filenames! because we will call them as command line arguments
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            subprocess.Popen(["python", "import_db.py", file_path])
            flash('File uploaded. Will be imported soon. follow from DB Status Page', 'info')
            return redirect('/')

    db = get_database_connection()

    cur = db.cursor()


    # get last 5000 sms
    cur.execute("SELECT * FROM PROCESSED_SMS ORDER BY date DESC LIMIT 5000")
    all_smss = cur.fetchall()
    smss = []
    for sms in all_smss:
        status, sender, message, answer, date = sms
        smss.append({'status': status, 'sender': sender, 'message': message, 'answer': answer, 'date': date})

    # collect some stats for the GUI
    try:
        cur.execute("SELECT count(*) FROM PROCESSED_SMS WHERE status = 'OK'")
        num_ok = cur.fetchone()[0]
    except: 
        num_ok = 'error'

    try:        
        cur.execute("SELECT count(*) FROM PROCESSED_SMS WHERE status = 'FAILURE'")
        num_failure = cur.fetchone()[0]
    except:
        num_failure = 'error'

    try:
        cur.execute("SELECT count(*) FROM PROCESSED_SMS WHERE status = 'DOUBLE'")
        num_double = cur.fetchone()[0]
    except:
        num_double = 'error'

    try:
        cur.execute("SELECT count(*) FROM PROCESSED_SMS WHERE status = 'NOT-FOUND'")
        num_notfound = cur.fetchone()[0]
    except:
        num_notfound = 'error'

    return render_template('index.html', data={'smss': smss, 'ok': num_ok, 'failure': num_failure, 'double': num_double,
                                               'notfound': num_notfound})

@app.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    """ user login: only for admin user (system has no other user than admin)
    Note: there is a 10 tries per minute limitation to admin login to avoid minimize password factoring"""
    if current_user.is_authenticated:
        return redirect('/')
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if password == config.PASSWORD and username == config.USERNAME:
            login_user(user)
            return redirect('/')
        else:
            return abort(401)
    else:
        return render_template('login.html')


@app.route(f"/v1/{config.REMOTE_CALL_API_KEY}/check_one_serial/<serial>", methods=["GET"])
def check_one_serial_api(serial):
    """ to check whether a serial number is valid or not using api
    caller should use something like /v1/ABCDSECRET/cehck_one_serial/AA10000
    answer back json which is status = DOUBLE, FAILURE, OK, NOT-FOUND
    """
    status, answer = check_serial(serial)
    ret = {'status': status, 'answer': answer}
    return jsonify(ret), 200


@app.route("/check_one_serial", methods=["POST"])
@login_required
def check_one_serial():
    """ to check whether a serial number is valid or not"""
    serial_to_check = request.form["serial"]
    status, answer = check_serial(serial_to_check)
    flash(f'{status} - {answer}', 'info')

    return redirect('/')


@app.route("/logout")
@login_required
def logout():
    """ logs out the admin user"""
    logout_user()
    flash('Logged out', 'success')
    return redirect('/login')


#
@app.errorhandler(401)
def unauthorized(error):
    """ handling login failures"""
    flash('Login problem', 'danger')
    return redirect('/login')


# callback to reload the user object
@login_manager.user_loader
def load_user(userid):
    return User(userid)


@app.route('/v1/ok')
def health_check():
    """ for system health check. calling it will answer with json message: ok """
    ret = {'message': 'ok'}
    return jsonify(ret), 200


def get_database_connection():
    """connects to the MySQL database and returns the connection"""
    return MySQLdb.connect(host=config.MYSQL_HOST,
                           user=config.MYSQL_USERNAME,
                           passwd=config.MYSQL_PASSWORD,
                           db=config.MYSQL_DB_NAME,
                           charset='utf8')


def send_sms(receptor, message):
    """ gets a MSISDN and a messaage, then uses KaveNegar to send sms."""
    url = f'https://api.kavenegar.com/v1/{config.API_KEY}/sms/send.json'
    data = {"message": message,
            "receptor": receptor}
    res = requests.post(url, data)


def _remove_non_alphanum_char(string):
    return re.sub(r'\W+', '', string)


def _translate_numbers(current, new, string):
    translation_table = str.maketrans(current, new)
    return string.translate(translation_table)

def normalize_string(serial_number, fixed_size=30):
    """ gets a serial number and standardize it as following:
    >> converts(removes others) all chars to English upper letters and numbers
    >> adds zeros between letters and numbers to make it fixed length """

    serial_number = _remove_non_alphanum_char(serial_number)
    serial_number = serial_number.upper()

    persian_numerals = '۱۲۳۴۵۶۷۸۹۰'
    arabic_numerals = '١٢٣٤٥٦٧٨٩٠'
    english_numerals = '1234567890'

    serial_number = _translate_numbers(persian_numerals, english_numerals, serial_number)
    serial_number = _translate_numbers(arabic_numerals, english_numerals, serial_number)

    all_digit = "".join(re.findall("\d", serial_number))
    all_alpha = "".join(re.findall("[A-Z]", serial_number))

    missing_zeros = "0" * (fixed_size - len(all_alpha + all_digit))

    return f"{all_alpha}{missing_zeros}{all_digit}"



def check_serial(serial):
    """ gets one serial number and returns appropriate
    answer to that, after looking it up in the db
    """
    original_serial = serial
    serial = normalize_string(serial)

    db = get_database_connection()

    with db.cursor() as cur:
        results = cur.execute("SELECT * FROM invalids WHERE invalid_serial = %s", (serial,))
        if results > 0:
            answer = dedent(f"""\
                {original_serial}
                این شماره هولوگرام یافت نشد. لطفا دوباره سعی کنید  و یا با واحد پشتیبانی تماس حاصل فرمایید.
                ساختار صحیح شماره هولوگرام بصورت دو حرف انگلیسی و 7 یا 8 رقم در دنباله آن می باشد. مثال:
                FA1234567
                شماره تماس با بخش پشتیبانی فروش شرکت التک:
                021-22038385""")

            return 'FAILURE', answer

        results = cur.execute("SELECT * FROM serials WHERE start_serial <= %s and end_serial >= %s", (serial, serial))
        if results > 1:
            answer = dedent(f"""\
                {original_serial}
                این شماره هولوگرام مورد تایید است.
                برای اطلاعات بیشتر از نوع محصول با بخش پشتیبانی فروش شرکت التک تماس حاصل فرمایید:
                021-22038385""")
            return 'DOUBLE', answer
        elif results == 1:
            ret = cur.fetchone()
            desc = ret[2]
            ref_number = ret[1]
            date = ret[5].date()
            answer = dedent(f"""\
                {original_serial}
                {ref_number}
                {desc}
                Hologram date: {date}
                Genuine product of Schneider Electric
                شماره تماس با بخش پشتیبانی فروش شرکت التک:
                021-22038385""")
            return 'OK', answer


    answer = dedent(f"""\
        {original_serial}
        این شماره هولوگرام یافت نشد. لطفا دوباره سعی کنید  و یا با واحد پشتیبانی تماس حاصل فرمایید.
        ساختار صحیح شماره هولوگرام بصورت دو حرف انگلیسی و 7 یا 8 رقم در دنباله آن می باشد. مثال:
        FA1234567
        شماره تماس با بخش پشتیبانی فروش شرکت التک:
        021-22038385""")

    return 'NOT-FOUND', answer


@app.route(f'/v1/{CALL_BACK_TOKEN}/process', methods=['POST'])
def process():
    """ this is a call back from KaveNegar. Will get sender and message and
    will check if it is valid, then answers back.
    This is secured by 'CALL_BACK_TOKEN' in order to avoid mal-intended calls
    """
    data = request.form
    sender = data["from"]
    message = data["message"]

    status, answer = check_serial(message)

    db = get_database_connection()

    cur = db.cursor()

    log_new_sms(status, sender, message, answer, cur)
    
    db.commit()
    db.close()

    send_sms(sender, answer)
    ret = {"message": "processed"}
    return jsonify(ret), 200

def log_new_sms(status, sender, message, answer, cur):
    if len(message) > 40:
        return
    now = time.strftime('%Y-%m-%d %H:%M:%S')
    cur.execute("INSERT INTO PROCESSED_SMS (status, sender, message, answer, date) VALUES (%s, %s, %s, %s, %s)", (status, sender, message, answer, now))
    
@app.errorhandler(404)
def page_not_found(error):
    """ returns 404 page"""
    return render_template('404.html'), 404



def create_sms_table():
    """Ctreates PROCESSED_SMS table on database if it's not exists."""

    db = get_database_connection()

    cur = db.cursor()

    try:
        cur.execute("""CREATE TABLE IF NOT EXISTS PROCESSED_SMS (
            status ENUM('OK', 'FAILURE', 'DOUBLE', 'NOT-FOUND'),
            sender CHAR(20),
            message VARCHAR(400),
            answer VARCHAR(400),
            date DATETIME, INDEX(date, status));""")
        db.commit()
    except Exception as e:
        flash(f'Error creating PROCESSED_SMS table; {e}', 'danger')
        
    db.close()


if __name__ == "__main__":
    create_sms_table()
    app.run("0.0.0.0", 5000, debug=False)
