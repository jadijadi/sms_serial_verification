from flask import Flask, jsonify, request
from pandas import read_excel
import requests
import re
import sqlite3
import config

app = Flask(__name__)

@app.route('/v1/ok')
def health_check():
    ret = {'message': 'ok'}
    return jsonify(ret), 200

def send_sms(receptor, message):
    """ this function will get a MSISDN and a messaage, then
    uses KaveNegar to send sms.
    """
    url = f'https://api.kavenegar.com/v1/{config.API_KEY}/sms/send.json'
    data = {"message": message,
            "receptor": receptor}
    res = requests.post(url, data)
    print(f"message *{message}* sent. status code is {res.status_code}")         

def normalize_string(str):
    from_char = '۱۲۳۴۵۶۷۸۹۰'
    to_char = '1234567890'
    for i in range(len(from_char)):
        str = str.replace(from_char[i], to_char[i])
    str = str.upper()
    str = re.sub(r'\W+', '', str) # remove any non alphanumeric character
    return str

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
    # TODO: do some normaliziation

    ## our sqlite database wil contain two tables: serials and invalids
    conn = sqlite3.connect(config.DATABASE_FILE_PATH)
    cur = conn.cursor()

    # remove the serials table if exists, then craete the new one
    cur.execute('DROP TABLE IF EXISTS serials')
    cur.execute("""CREATE TABLE IF NOT EXISTS serials (
        id INTEGER PRIMARY KEY,
        ref TEXT,
        desc TEXT,
        start_serial TEXT,
        end_serial TEXT,
        date DATE);""")
    conn.commit()

    df = read_excel(filepath, 0) 
    serials_counter = 0
    for index, (line, ref, desc, start_serial, end_serial, date) in df.iterrows():
        start_serial = normalize_string(start_serial)
        end_serial = normalize_string(end_serial)
        query = f'INSERT INTO serials VALUES ("{line}", "{ref}", "{desc}", "{start_serial}", "{end_serial}", "{date}");'
        cur.execute(query)
        # TODO: do some more error handling
        if serials_counter % 10:
            conn.commit()
        serials_counter += 1
    conn.commit()

    # now lets save the invalid serials.

    # remove the invalid table if exists, then craete the new one
    cur.execute('DROP TABLE IF EXISTS invalids')
    cur.execute("""CREATE TABLE IF NOT EXISTS invalids (
        invalid_serial TEXT PRIMARY KEY);""")
    conn.commit()
    invalid_counter = 0
    df = read_excel(filepath, 1) 
    for index, (failed_serial, ) in df.iterrows():
        query = f'INSERT INTO invalids VALUES ("{failed_serial}")'
        cur.execute(query)
        # TODO: do some more error handling
        if invalid_counter % 10 == 0:
            conn.commit()
        invalid_counter += 1
    conn.commit()

    conn.close()

    return (serials_counter, invalid_counter)

def check_serial(serial):
    """ this function will get one serial number and return appropriate
    answer to that, after consulting the db
    """
    conn = sqlite3.connect(config.DATABASE_FILE_PATH)
    cur = conn.cursor()

    query = f"SELECT * FROM invalids WHERE invalid_serial == '{serial}'"
    results = cur.execute(query)
    if len(results.fetchall()) == 1:
        return 'this serial is among failed ones' #TODO: return the string provided by the customer

    query = f"SELECT * FROM serials WHERE start_serial < '{serial}' and end_serial > '{serial}';"
    print (query)
    results = cur.execute(query)
    if len(results.fetchall()) == 1:
        return 'I found your serial' # TODO: return the string provided by the customer

    return 'it was not in the db'


@app.route('/v1/process', methods=['POST'])
def process():
    """ this is a call back from KaveNegar. Will get sender and message and
    will check if it is valid, then answers back
    """
    data = request.form
    sender = data["from"]
    message = normalize_string(data["message"])
    print(f'received {message} from {sender}') #TODO: logging

    answer = check_serial(message)

    send_sms(sender, answer)
    ret = {"message": "processed"}
    return jsonify(ret), 200

if __name__ == "__main__":
    import_database_from_excel('../data.xlsx')
    print (check_serial('JJ1000002'))
    app.run("0.0.0.0", 5000, debug=True)
    
