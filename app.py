from flask import Flask, jsonify, request
from pandas import read_excel
import requests
import config

app = Flask(__name__)

@app.route('/v1/process', methods=['POST'])
def process():
    """ this is a call back from KaveNegar. Will get sender and message and
    will check if it is valid, then answers back
    """
    data = request.form
    sender = data["from"]
    message = data["message"]
    print(f'received {message} from {sender}')
    send_sms(sender, 'Hi '+message)
    ret = {"message": "processed"}
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

def import_database_from_excel(filepath):
    """ gets an excel file name and imports lookup data (data and failures) from it"""
    # df contains lookup data in the form of 
    # Row	Reference Number	Description	Start Serial	End Serial	Date
    df = read_excel(filepath, 0) 
    for index, (line, ref, desc, start_serial, end_serial, date) in df.iterrows(): 
        print (line, ref, desc, start_serial, end_serial, date)

    df = read_excel(filepath, 1) # sheet one contains failed serial numbers. only one column
    for index, (failed_serial_row) in df.iterrows():
        failed_serial = failed_serial_row[0]
        print(failed_serial)


def check_serial():
    pass

if __name__ == "__main__":
    #app.run("0.0.0.0", 5000, debug=True)
    import_database_from_excel('/tmp/data.xlsx')
