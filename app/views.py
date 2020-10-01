import os
import re
from textwrap import dedent
import subprocess
import time
import requests
import MySQLdb

from flask import (
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for
)
from flask_login import (
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user
)
from werkzeug.utils import secure_filename

from app import app, db, limiter, login_manager
from app.models import User. Logs, Serials, Invalids, ProcessedSMS
from app.tools import normalize_string, _remove_non_alphanum_char, _translate_numbers, allowed_file, send_sms


user = User(0)


@app.route('/db_status/', methods=['GET'])
@login_required
def db_status():
    """ show some status about the DB """
    try:
        num_serials = len(Serials.query.all())
    except:
        num_serials = 'can not query serials count'
    try:
        num_invalids = len(Invalids.query.all())
    except:
        num_invalids = 'can not query invalid count'
    try:
        log_import = Logs.query.with_entities(Logs.log_value).filter_by(log_name='import').all()
    except:
        log_import = 'can not read import log results... yet'
    try:
        log_filename = Logs.query.with_entities(Logs.log_value).filter_by(log_name='db_filename').all()
    except:
        log_filename = 'can not read db filename from database'
    try:
        log_db_check = Logs.query.with_entities(Logs.log_value).filter_by(log_name='db_check').all()
    except:
        log_db_check = 'Can not read db_check logs... yet'



    return render_template(
        'db_status.html',
        data={
            'serials': num_serials,
            'invalids': num_invalids,
            'log_import': log_import,
            'log_db_check': log_db_check,
            'log_filename': log_filename})


@app.route('/', methods=['GET', 'POST'])
@login_required
def home():
    """ creates database if method is post
        otherwise shows the homepage with some stats.
        see import_database_from_excel() for more details on database creation
    """
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
            # TODO: is space find in a file name? check if it works
            filename = secure_filename(file.filename)
            # no space in filenames! because we will call them as command line
            # arguments
            filename.replace(' ', '_')
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            subprocess.Popen(["python", "import_db.py", file_path])
            flash(
                'File uploaded. Will be imported soon. follow from DB Status Page',
                'info')
            return redirect(url_for('home'))

    # get last 5000 sms
    all_smss = ProcessedSMS.query.order_by(ProcessedSMS.date.desc()).limit(5000).all()
    smss = []
    for sms in all_smss:
        status, sender, message, answer, date = sms
        smss.append({'status': status,
                     'sender': sender,
                     'message': message,
                     'answer': answer,
                     'date': date
                     })

    try:
        num_ok = len(ProcessedSMS.query.filter_by(status='OK').all())
    except:
        num_ok = 'error'
    try:
        num_failure = len(ProcessedSMS.query.filter_by(status='FAILURE').all())
    except:
        num_failure = 'error'
    try:
        num_double = len(ProcessedSMS.query.filter_by(status='DOUBLE').all())
    except:
        num_double = 'error'
    try:
        num_notfound = len(ProcessedSMS.query.filter_by(status='NOT-FOUND').all())
    except:
        num_notfound = 'error'



    # collect some stats for the GUI
    return render_template(
            'index.html',
            data={
                'smss': smss,
                'ok': num_ok,
                'failure': num_failure,
                'double': num_double,
                'notfound': num_notfound
            })


@app.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    """ user login: only for admin user (system has no other user than admin)
        Note: there is a 10 tries per minute limitation to admin login
        to avoid minimize password factoring
    """
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if password == app.config['PASSWORD'] and \
                username == app.config['USERNAME']:
            login_user(user)
            return redirect(url_for('home'))
        else:
            return abort(401)
    else:
        return render_template('login.html')


@app.route(f"/v1/{app.config['REMOTE_CALL_API_KEY']}/check_one_serial/<serial>")
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

    return redirect(url_for('home'))


@app.route("/logout")
@login_required
def logout():
    """ logs out the admin user"""
    logout_user()
    flash('Logged out', 'success')
    return redirect(url_for('login'))


@app.errorhandler(401)
def unauthorized(error):
    """ handling login failures"""
    flash('Login problem', 'danger')
    return redirect(url_for('login'))


@app.route('/v1/ok')
def health_check():
    """ for system health check.
        calling it will answer with json message: ok
    """
    ret = {'message': 'ok'}
    return jsonify(ret), 200


def check_serial(serial):
    """ gets one serial number and returns appropriate
    answer to that, after looking it up in the db
    """
    original_serial = serial
    serial = normalize_string(serial)

    query = Invalids.query.filter_by(invalid_serial=serial).all()
    results = len(query)
    if results > 0:
        answer = dedent(f"""\
            {original_serial}
            این شماره هولوگرام یافت نشد. لطفا دوباره سعی کنید  و یا با واحد پشتیبانی تماس حاصل فرمایید.
            ساختار صحیح شماره هولوگرام بصورت دو حرف انگلیسی و 7 یا 8 رقم در دنباله آن می باشد. مثال:
            FA1234567
            شماره تماس با بخش پشتیبانی فروش شرکت التک:
            021-22038385""")

        return 'FAILURE', answer

    query = Serials.query.filter(
                Serials.start_serial <= serial,
                Serials.end_serial >= serial).all()
    results = len(query)
    if results > 1:
        answer = dedent(f"""\
            {original_serial}
            این شماره هولوگرام مورد تایید است.
            برای اطلاعات بیشتر از نوع محصول با بخش پشتیبانی فروش شرکت التک تماس حاصل فرمایید:
            021-22038385""")
        return 'DOUBLE', answer
    elif results == 1:
        ret = query[0]
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


@app.route(f"/v1/{app.config['CALL_BACK_TOKEN']}/process", methods=['POST'])
def process():
    """ this is a call back from KaveNegar. Will get sender and message and
    will check if it is valid, then answers back.
    This is secured by 'CALL_BACK_TOKEN' in order to avoid mal-intended calls
    """
    data = request.form
    sender = data["from"]
    message = data["message"]

    status, answer = check_serial(message)
    log_new_sms(status, sender, message, answer, cur=None)

    send_sms(sender, answer)
    ret = {"message": "processed"}
    return jsonify(ret), 200


def log_new_sms(status, sender, message, answer, cur):
    if len(message) > 40:
        return
    now = time.strftime('%Y-%m-%d %H:%M:%S')
    new_sms = ProcessedSMS(
        status=status,
        sender=sender,
        message=message,
        answer=answer,
        date=now)
    db.session.add(new_sms)
    db.session.commit()


@app.errorhandler(404)
def page_not_found(error):
    """ returns 404 page"""
    return render_template('404.html'), 404
