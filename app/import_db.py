import datetime
import os
import time
import sys
import re

import config
import MySQLdb
from pandas import read_excel

MAX_FLASH = 100

def _remove_non_alphanum_char(string):
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

    all_digit = "".join(re.findall("\d", serial_number))
    all_alpha = "".join(re.findall("[A-Z]", serial_number))

    missing_zeros = "0" * (fixed_size - len(all_alpha + all_digit))

    return f"{all_alpha}{missing_zeros}{all_digit}"



def get_database_connection():
    """connects to the MySQL database and returns the connection"""
    return MySQLdb.connect(host=config.MYSQL_HOST,
                           user=config.MYSQL_USERNAME,
                           passwd=config.MYSQL_PASSWORD,
                           db=config.MYSQL_DB_NAME,
                           charset='utf8')

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

    db = get_database_connection()

    cur = db.cursor()

    total_flashes = 0
    output = []

    try:
        cur.execute('DROP TABLE IF EXISTS logs;')
        cur.execute("""CREATE TABLE logs (            
            log_name CHAR(200),
            log_value MEDIUMTEXT);
            """)
        db.commit()
    except Exception as e:
        print("dropping logs")
        output.append(
            f'problem dropping and creating new table for logs in database; {e}')


    # remove the serials table if exists, then create the new one
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
    except Exception as e:
        print("problem dropping serials")
        output.append(
            f'problem dropping and creating new table serials in database; {e}')
    
    cur.execute("INSERT INTO logs VALUES ('db_filename', %s)", (filepath, ))
    db.commit()

    # remove the invalid table if exists, then create the new one
    try:
        cur.execute('DROP TABLE IF EXISTS invalids;')
        cur.execute("""CREATE TABLE invalids (
            invalid_serial CHAR(30), INDEX(invalid_serial));""")
        db.commit()
    except Exception as e:
        output.append(f'Error dropping and creating INVALIDS table; {e}')

    # insert some place holder logs
    cur.execute("INSERT INTO logs VALUES ('import', %s)",
                ('Import started. logs will appear when its done', ))
    cur.execute("INSERT INTO logs VALUES ('db_check', %s)", ('DB check will be run after the insert is finished', ))
    db.commit()

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
            cur.execute("INSERT INTO serials VALUES (%s, %s, %s, %s, %s, %s);", (
                line, ref, description, start_serial, end_serial, date)
            )
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
    db.commit()

    # now lets save the invalid serials.

    invalid_counter = 1
    line_number = 1
    df = read_excel(filepath, 1)
    for _, (failed_serial,) in df.iterrows():
        line_number += 1
        try:
            failed_serial = normalize_string(failed_serial)
            cur.execute('INSERT INTO invalids VALUES (%s);', (failed_serial,))
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
    db.commit()

    # save the logs
    output.append(f'Inserted {serials_counter} serials and {invalid_counter} invalids')
    output.reverse()
    cur.execute("UPDATE logs SET log_value = %s WHERE log_name = 'import'", ('\n'.join(output), ))
    db.commit()

    db.close()

    return


def db_check():
    """ will do some sanity checks on the db and will flash the errors """

    db = get_database_connection()
    cur = db.cursor()
    cur.execute("INSERT INTO logs VALUES ('db_check', %s)",
                ('DB check started... wait for the results. it may take a while', ))
    db.commit()

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



    cur.execute("SELECT id, start_serial, end_serial FROM serials")

    raw_data = cur.fetchall()
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
    
    cur.execute("UPDATE logs SET log_value = %s WHERE log_name = 'db_check'", (output, ))
    db.commit()

    db.close()


filepath = sys.argv[1]

import_database_from_excel(filepath)
db_check()

os.remove(filepath)
