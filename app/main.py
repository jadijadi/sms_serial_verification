import datetime
import os
import re
import time
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


# some protected url
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
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            rows, failures = import_database_from_excel(file_path)
            flash(f'Imported {rows} rows of serials and {failures} rows of failure', 'success')
            os.remove(file_path)
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
    cur.execute("SELECT count(*) FROM PROCESSED_SMS WHERE status = 'OK'")
    num_ok = cur.fetchone()[0]

    cur.execute("SELECT count(*) FROM PROCESSED_SMS WHERE status = 'FAILURE'")
    num_failure = cur.fetchone()[0]

    cur.execute("SELECT count(*) FROM PROCESSED_SMS WHERE status = 'DOUBLE'")
    num_double = cur.fetchone()[0]

    cur.execute("SELECT count(*) FROM PROCESSED_SMS WHERE status = 'NOT-FOUND'")
    num_notfound = cur.fetchone()[0]

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


@app.route("/dbcheck")
@login_required
def db_check():
    """ will do some sanity checks on the db and will flash the errors """

    def collision(s1, e1, s2, e2):
        if s2 <= s1 <= e2:
            return True
        if s2 <= e1 <= e2:
            return True
        if s1 <= s2 <= e1:
            return True
        if s1 <= e2 <= e1:
            return True
        return False

    def separate(input_string):
        """ gets AA0000000000000000000000000090 and returns AA, 90 """
        digit_part = ''
        alpha_part = ''
        for character in input_string:
            if character.isalpha():
                alpha_part += character
            elif character.isdigit():
                digit_part += character
        return alpha_part, int(digit_part)


    db = get_database_connection()
    cur = db.cursor()

    cur.execute("SELECT id, start_serial, end_serial FROM serials")

    raw_data = cur.fetchall()

    data = {}
    flashed = 0
    for row in raw_data:
        id_row, start_serial, end_serial = row
        start_serial_alpha, start_serial_digit = separate(start_serial)
        end_serial_alpha, end_serial_digit = separate(end_serial)
        if start_serial_alpha != end_serial_alpha:
            flashed += 1
            if flashed < MAX_FLASH:
                flash(f'start serial and end serial of row {id_row} start with different letters', 'danger')
            elif flashed == MAX_FLASH:
                flash('too many starts with different letters', 'danger')
        else:
            if start_serial_alpha not in data:
                data[start_serial_alpha] = []
            data[start_serial_alpha].append(
                (id_row, start_serial_digit, end_serial_digit))

    flashed = 0
    for letters in data:
        for i in range(len(data[letters])):
            for j in range(i+1, len(data[letters])):
                id_row1, ss1, es1 = data[letters][i]
                id_row2, ss2, es2 = data[letters][j]
                if collision(ss1, es1, ss2, es2):
                    flashed += 1
                    if flashed < MAX_FLASH:
                        flash(f'there is a collision between row ids {id_row1} and {id_row2}', 'danger')
                    elif flashed == MAX_FLASH:
                        flash(f'Too many collisions', 'danger')

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
    print(f"message *{message}* sent. status code is {res.status_code}")


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



def import_database_from_excel(filepath):
    """ gets an excel file name and imports lookup data (data and failures) from it
    the first (0) sheet contains serial data like:
     Row	Reference Number	Description	Start Serial	End Serial	Date
    and the 2nd (1) contains a column of invalid serials. 

    This data will be writeen into the sqlite database located at config.DATABASE_FILE_PATH
    in two tables. "serials" and "invalids"

    returns two integers: (number of serial rows, number of invalid rows)
    """
    # df contains lookup data in the form of
    # Row	Reference Number	Description	Start Serial	End Serial	Date

    db = get_database_connection()

    cur = db.cursor()

    total_flashes = 0

    # remove the serials table if exists, then craete the new one
    try:
        cur.execute('DROP TABLE IF EXISTS serials;')
        cur.execute("""CREATE TABLE serials (
            id INTEGER PRIMARY KEY,
            ref VARCHAR(200),
            description VARCHAR(200),
            start_serial CHAR(30),
            end_serial CHAR(30),
            date DATETIME, INDEX(start_serial, end_serial));""")
        db.commit()
    except Exception as e:
        flash(f'problem dropping and creating new table in database; {e}', 'danger')

    df = read_excel(filepath, 0)
    serials_counter = 1
    line_number = 1
    
    for _ , (line, ref, description, start_serial, end_serial, date) in df.iterrows():
        line_number += 1        
        try:
            start_serial = normalize_string(start_serial)
            end_serial = normalize_string(end_serial)
            cur.execute("INSERT INTO serials VALUES (%s, %s, %s, %s, %s, %s);", (
                line, ref, description, start_serial, end_serial, date)
                        )                        
            serials_counter += 1
        except Exception as e:
            total_flashes += 1
            if total_flashes < MAX_FLASH:
                flash(
                    f'Error inserting line {line_number} from serials sheet SERIALS, {e}',
                    'danger')
            elif total_flashes == MAX_FLASH:
                flash(f'Too many errors!', 'danger')
        if line_number % 1000 == 0:
            try:
                db.commit()
            except Exception as e:
                flash(f'problem commiting serials into db around {line_number} (or previous 20 ones); {e}')
    db.commit()

    # now lets save the invalid serials.
    # remove the invalid table if exists, then create the new one
    try:
        cur.execute('DROP TABLE IF EXISTS invalids;')
        cur.execute("""CREATE TABLE invalids (
            invalid_serial CHAR(30), INDEX(invalid_serial));""")
        db.commit()
    except Exception as e:
        flash(f'Error dropping and creating INVALIDS table; {e}', 'danger')

    invalid_counter = 1
    line_number = 1
    df = read_excel(filepath, 1)
    for _ , (failed_serial,) in df.iterrows():
        line_number += 1        
        try:
            failed_serial = normalize_string(failed_serial)
            cur.execute('INSERT INTO invalids VALUES (%s);', (failed_serial,))
            invalid_counter += 1
        except Exception as e:
            total_flashes += 1
            if total_flashes < MAX_FLASH:
                flash(
                    f'Error inserting line {line_number} from serials sheet SERIALS, {e}',
                    'danger')
            elif total_flashes == MAX_FLASH:
                flash(f'Too many errors!', 'danger')

        if line_number % 1000 == 0:
            try:
                db.commit()
            except Exception as e:
                flash(f'problem commiting invalid serials into db around {line_number} (or previous 20 ones); {e}')
    db.commit()
    db.close()

    return (serials_counter, invalid_counter)


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
            print(type(date))
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

    now = time.strftime('%Y-%m-%d %H:%M:%S')
    cur.execute("INSERT INTO PROCESSED_SMS (status, sender, message, answer, date) VALUES (%s, %s, %s, %s, %s)",
                (status, sender, message, answer, now))
    db.commit()
    db.close()

    send_sms(sender, answer)
    ret = {"message": "processed"}
    return jsonify(ret), 200


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
