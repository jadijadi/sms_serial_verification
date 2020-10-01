import datetime
import os
import time
import sys
import re
from app.models import Logs, Serials, Invalids, ProcessedSMS
from app import db
import MySQLdb
from pandas import read_excel
from app.tools import (
    normalize_string,
    _remove_non_alphanum_char,
    _translate_numbers,
    _translate_numbers,
    model_exists
)

MAX_FLASH = 100


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


    for model_class in (Logs, Serials, Invalids):
        if model_exists(model_class) == True:
            model_class.__table__.drop(bind=db.session.bind, checkfirst=True)
        if model_exists(model_class) == False:
            model_class.__table__.create(bind=db.session.bind, checkfirst=True)

    total_flashes = 0
    output = []
    first_log = Logs(log_name='db_filename', log_value=filepath)
    db.session.add(first_log)
    db.session.commit()

    # insert some place holder logs
    second_log = Logs(log_name='import', log_value='Import started. logs will appear when its done')
    third_log = Logs(log_name='db_check', log_value='DB check will be run after the insert is finished')
    db.session.add_all([second_log, third_log])
    db.session.commit()
    df = read_excel(filepath, 0)
    serials_counter = 1
    line_number = 1

    for _, (line, ref, description, start_serial, end_serial, date) in df.iterrows():
        line_number += 1
        if not ref or (ref != ref):
            ref = ""
        if not description or (description != description):
            description = ""
        if not date or (date != date):
            date = "7/2/12"
        try:
            start_serial = normalize_string(start_serial)
            end_serial = normalize_string(end_serial)
            new_serial = Serials(id=line, ref=ref, description=description, start_serial=start_serial, end_serial=end_serial, date=date)
            db.session.add(new_serial)
            db.session.commit()
            serials_counter += 1
        except Exception as e:
            total_flashes += 1
            if total_flashes < MAX_FLASH:                
                output.append(
                    f'Error inserting line {line_number} from serials sheet SERIALS, {e}')
            elif total_flashes == MAX_FLASH:
                output.append(f'Too many errors!')
        if line_number % 1000 == 0:
            try:
                db.commit()
            except Exception as e:
                output.append(
                    f'Problem commiting serials into db at around record {line_number} (or previous 1000 ones); {e}')
    db.session.commit()

    # now lets save the invalid serials.

    invalid_counter = 1
    line_number = 1
    df = read_excel(filepath, 1)
    for _, (failed_serial,) in df.iterrows():
        line_number += 1
        try:
            failed_serial = normalize_string(failed_serial)
            new_invalid = Invalids(invalid_serial=failed_serial)
            db.session.add(new_invalid)
            db.session.commit()
            invalid_counter += 1
        except Exception as e:
            total_flashes += 1
            if total_flashes < MAX_FLASH:
                output.append(
                    f'Error inserting line {line_number} from serials sheet SERIALS, {e}')
            elif total_flashes == MAX_FLASH:
                output.append(f'Too many errors!')

        if line_number % 1000 == 0:
            try:
                db.commit()
            except Exception as e:
                output.append(
                    f'Problem commiting invalid serials into db at around record {line_number} (or previous 1000 ones); {e}')
    db.session.commit()

    # save the logs
    output.append(f'Inserted {serials_counter} serials and {invalid_counter} invalids')
    output.reverse()
    logs = Logs.query.filter_by(log_name='import').all()
    for log in logs:
        log.log_value = '\n'.join(output)
    db.session.commit()


    return


def db_check():
    """ will do some sanity checks on the db and will flash the errors """

    # db = get_database_connection()
    # cur = db.cursor()
    new_log = Logs(log_name='db_check', log_value='DB check started... wait for the results. it may take a while')
    db.session.add(new_log)
    db.session.commit()
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


    serials = Serials.query.all()
    raw_data = [(serial.id, serial.start_serial, serial.end_serial) for serial in serials]
    all_problems = []

    data = {}
    flashed = 0
    for row in raw_data:
        id_row, start_serial, end_serial = row
        start_serial_alpha, start_serial_digit = separate(start_serial)
        end_serial_alpha, end_serial_digit = separate(end_serial)
        if start_serial_alpha != end_serial_alpha:
            all_problems.append(
                f'start serial and end serial of row {id_row} start with different letters')
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
                    all_problems.append(
                        f'there is a collision between row ids {id_row1} and {id_row2}')
    
    all_problems.reverse()
    output = "\n".join(all_problems)
    logs = Logs.query.filter_by(log_name='db_check').all()
    for log in logs:
        log.log_value = output
    db.session.commit()

filepath = sys.argv[1]

import_database_from_excel(filepath)
db_check()

os.remove(filepath)
