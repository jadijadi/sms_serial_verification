from flask import Flask, jsonify, request
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

def check_serial():
    pass

if __name__ == "__main__":
    app.run("0.0.0.0", 5000, debug=True)
