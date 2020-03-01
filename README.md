# sms_verification
This project is done for Altech as a educational series.

## How to run
1. Install python3, pip3, virtualenv, MySQL in your system.
2. Clone the project `https://github.com/jadijadi/sms_serial_verification && cd sms_serial_verification`
3. in the app folder, rename the `config.py.sample` to `config.py` and do proper changes.
4. db configs are in config.py. Create the db and grant all access to the specified user with specified password, but you also need to add this table to the database manually:
`CREATE TABLE PROCESSED_SMS (status ENUM('OK', 'FAILURE', 'DOUBLE', 'NOT-FOUND'), sender CHAR(20), message VARCHAR(400), answer VARCHAR(400), date DATETIME, INDEX(date, status));`
5. Create a virtualenve named build using `virtualenv -p python3 venv`
6. Connect to virtualenv using `source venv/bin/activate`
7. From the project folder, install packages using `pip install -r requirements.txt`
8. Now environment is ready. Run it by `python app/main.py`

### Or you can use Dockerfile 

### [click here to see TODO](./TODO.md)
