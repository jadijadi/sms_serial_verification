"""
  this file contains some util method
"""

def execute_and_fetchone(cursor, command, on_error_value="error"):
  """
  this method exce command on cursor and return zero index of fetchone method
  """
  if cursor is None:
    raise Exception("cursor is None. can't run {} on None cursor".format(command))
  try:
    cursor.execute(command)
    return cursor.fetchone()[0]
  except:
    return on_error_value
