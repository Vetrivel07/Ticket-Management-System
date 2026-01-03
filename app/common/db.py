from contextlib import contextmanager
from ..extensions import mysql

@contextmanager
def get_cursor(dict_cursor: bool = False):
    """
    Usage:
        with get_cursor() as cur:
            cur.execute(...)
            rows = cur.fetchall()

    dict_cursor=True returns dict rows if your MySQL driver supports it.
    """
    cur = None
    try:
        if dict_cursor:
            cur = mysql.connection.cursor()  # adjust if you later switch cursor types
        else:
            cur = mysql.connection.cursor()
        yield cur
    finally:
        if cur is not None:
            cur.close()
