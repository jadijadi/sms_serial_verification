from app import app
import re
import requests
import MySQLdb


def allowed_file(filename: str):
    """ checks the extension of the passed filename to be in the allowed extensions"""
    return '.' in filename and filename.rsplit(
        '.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def get_database_connection():
    """connects to the MySQL database and returns the connection"""
    return MySQLdb.connect(host=app.config['MYSQL_HOST'],
                           user=app.config['MYSQL_USERNAME'],
                           passwd=app.config['MYSQL_PASSWORD'],
                           db=app.config['MYSQL_DB_NAME'],
                           charset='utf8')


def send_sms(receptor, message):
    """ gets a MSISDN and a messaage, then uses KaveNegar to send sms."""
    url = f"https://api.kavenegar.com/v1/{app.config['API_KEY']}/sms/send.json"
    data = {"message": message,
            "receptor": receptor}
    res = requests.post(url, data)


def _remove_non_alphanum_char(string: str) -> str:
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

    serial_number = _translate_numbers(
        persian_numerals, english_numerals, serial_number)
    serial_number = _translate_numbers(
        arabic_numerals, english_numerals, serial_number)

    all_digit = "".join(re.findall(r"\d", serial_number))
    all_alpha = "".join(re.findall("[A-Z]", serial_number))

    missing_zeros = "0" * (fixed_size - len(all_alpha + all_digit))

    return f"{all_alpha}{missing_zeros}{all_digit}"
