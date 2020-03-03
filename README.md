# sms_verification
This project is done for Altech (Schneider Electric Iran) as an educational series.

## How to run
1. Install python3, pip3, virtualenv, MySQL in your system.
2. Clone the project `https://github.com/jadijadi/sms_serial_verification && cd sms_serial_verification`
3. in the app folder, rename the `config.py.sample` to `config.py` and do proper changes.
4. db configs are in config.py. Create the db and grant all access to the specified user with specified password.
5. Create a virtualenve named build using `virtualenv -p python3 venv`
6. Connect to virtualenv using `source venv/bin/activate`
7. From the project folder, install packages using `pip install -r requirements.txt`
8. Now environment is ready. Run it by `python app/main.py`

## Example of creating db and granting access:
```
CREATE DATABASE smsmysql;
USE smsmysql;
CREATE USER 'smsmysql'@'localhost' IDENTIFIED BY 'test' PASSWORD NEVER EXPIRE;
GRANT ALL PRIVILEGES ON smsmysql.* TO 'smsmysql'@'localhost';
```

