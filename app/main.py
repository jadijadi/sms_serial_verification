import re
import os
import time
import requests

from flask import Flask, flash, jsonify, request, Response, redirect, url_for, abort, render_template
from flask_login import LoginManager, UserMixin, login_required, login_user, logout_user, current_user
from pandas import read_excel
from werkzeug.utils import secure_filename
import MySQLdb
import config
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

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


@app.route("/check_one_serial", methods=["POST"])
@login_required
def check_one_serial():
    """ to check whether a serial number is valid or not"""
    serial_to_check = request.form["serial"]
    status, answer = check_serial(normalize_string(serial_to_check))
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
def page_not_found(error):
    """ handling login failures"""
    flash('Login problem', 'danger')
    return redirect('/login')


# callback to reload the user object
@login_manager.user_loader
def load_user(userid):
    return User(userid)


@app.route('/v1/ok')
def health_check():
    ret = {'message': 'ok'}
    return jsonify(ret), 200


def get_database_connection():
    """connects to the MySQL database and returns the connection"""
    return MySQLdb.connect(host=config.MYSQL_HOST, user=config.MYSQL_USERNAME,
                           passwd=config.MYSQL_PASSWORD, db=config.MYSQL_DB_NAME)


def send_sms(receptor, message):
    """ gets a MSISDN and a messaage, then uses KaveNegar to send sms."""
    url = f'https://api.kavenegar.com/v1/{config.API_KEY}/sms/send.json'
    data = {"message": message,
            "receptor": receptor}
    res = requests.post(url, data)
    print(f"message *{message}* sent. status code is {res.status_code}")


def normalize_string(serial_number, fixed_size=30):
    """ gets a serial number and standardize it as following:
    >> converts(removes others) all chars to English upper letters and numbers
    >> adds zeros between letters and numbers to make it fixed length """
    # remove any non-alphanumeric character
    serial_number = re.sub(r'\W+', '', serial_number)
    serial_number = serial_number.upper()

    # replace persian and arabic numeric chars to standard format
    from_persian_char = '۱۲۳۴۵۶۷۸۹۰'
    from_arabic_char = '١٢٣٤٥٦٧٨٩٠'
    to_char = '1234567890'
    for i in range(len(to_char)):
        serial_number = serial_number.replace(from_persian_char[i], to_char[i])
        serial_number = serial_number.replace(from_arabic_char[i], to_char[i])

    # separate the alphabetic and numeric part of the serial number
    all_alpha = ''
    all_digit = ''
    for c in serial_number:
        if c.isalpha():
            all_alpha += c
        elif c.isdigit():
            all_digit += c

    # add zeros between alphabetic and numeric parts to standardaize the length of the serial number
    missing_zeros = fixed_size - len(all_alpha) - len(all_digit)
    serial_number = all_alpha + '0' * missing_zeros + all_digit

    return serial_number


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

    # TODO: make sure that the data is imported correctly, we need to backup the old one

    db = get_database_connection()

    cur = db.cursor()

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
    except:
        flash('problem dropping and creating new table in database', 'danger')

    df = read_excel(filepath, 0)
    serials_counter = 1
    total_flashes = 0
    for index, (line, ref, description, start_serial, end_serial, date) in df.iterrows():
        serials_counter += 1
        try:
            start_serial = normalize_string(start_serial)
            end_serial = normalize_string(end_serial)
            cur.execute("INSERT INTO serials VALUES (%s, %s, %s, %s, %s, %s);", (
                line, ref, description, start_serial, end_serial, date)
                        )
            db.commit()
        except:
            total_flashes += 1
            if total_flashes < MAX_FLASH:
                flash(f'Error insering line {serials_counter} from serials sheet SERIALS', 'danger')
            else:
                flash(f'Too many errors!', 'danger')

    # now lets save the invalid serials.
    # remove the invalid table if exists, then create the new one
    try:
        cur.execute('DROP TABLE IF EXISTS invalids;')
        cur.execute("""CREATE TABLE invalids (
            invalid_serial CHAR(30), INDEX(invalid_serial));""")
        db.commit()
    except:
        flash('Error dropping and creating INVALIDS table', 'danger')

    invalid_counter = 1
    df = read_excel(filepath, 1)
    for index, (failed_serial,) in df.iterrows():
        invalid_counter += 1
        try:
            failed_serial = normalize_string(failed_serial)
            cur.execute('INSERT INTO invalids VALUES (%s);', (failed_serial,))
            db.commit()
        except:
            total_flashes += 1
            if total_flashes < MAX_FLASH:
                flash(
                    f'Error insering line {invalid_counter} from serials sheet INVALIDS',
                    'danger')
            else:
                flash(f'Too many errors!', 'danger')

    db.close()

    return (serials_counter, invalid_counter)


def check_serial(serial):
    """ gets one serial number and returns appropriate
    answer to that, after looking it up in the db
    """

    db = get_database_connection()

    cur = db.cursor()

    results = cur.execute("SELECT * FROM invalids WHERE invalid_serial = %s", (serial,))
    if results > 0:
        db.close()
        return 'FAILURE', 'this serial is among failed ones'  # TODO: return the string provided by the customer

    results = cur.execute("SELECT * FROM serials WHERE start_serial <= %s and end_serial >= %s", (serial, serial))
    if results > 1:
        db.close()
        return 'DOUBLE', 'I found your serial'  # TODO: fix with proper message
    elif results == 1:
        ret = cur.fetchone()
        desc = ret[2]
        db.close()
        return 'OK', 'I found your serial: ' + desc  # TODO: return the string provided by the customer

    db.close()
    return 'NOT-FOUND', 'it was not in the db'


@app.route(f'/v1/{CALL_BACK_TOKEN}/process', methods=['POST'])
def process():
    """ this is a call back from KaveNegar. Will get sender and message and
    will check if it is valid, then answers back.
    This is secured by 'CALL_BACK_TOKEN' in order to avoid mal-intended calls
    """
    data = request.form
    sender = data["from"]
    message = normalize_string(data["message"])
    print(f'received {message} from {sender}')

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
def page_not_found():
    """ returns 404 page"""
    return render_template('404.html'), 404


if __name__ == "__main__":
    # import_database_from_excel('../data.xlsx')
    # process('sender', normalize_string('JJ1000000'))
    # process('sender', normalize_string('JM101'))
    # process('sender', normalize_string('JJ101'))
    # process('sender', normalize_string('chert'))
    # process('sender', normalize_string('JM199'))
    app.run("0.0.0.0", 5000, debug=True)
