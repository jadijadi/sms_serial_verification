from flask import Flask
app = Flask(__name__)


@app.route('/')
def main_page():
    ''' This is the main page of the site
    '''
    return 'Hello'
