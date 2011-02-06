from pysqlite2 import dbapi2 as sqlite3
import xbmc

__author__ = 'twinther'

class Database(object):
    def __init__(self):
        self.db_file = xbmc.translatePath('special://profile/Database/MyVideos34.db')
        self.conn = sqlite3.connect(self.db_file)
        self.conn.row_factory = sqlite_dict_factory

    def __del__(self):
        self.conn.close()
        print "Database closed"

    def fetchall(self, sql, parameters = tuple()):
        if not isinstance(parameters, tuple):
            parameters = [parameters]

        c = self.conn.cursor()
        c.execute(sql, parameters)
        result = c.fetchall()

        return result

    def fetchone(self, sql, parameters = tuple()):
        if not isinstance(parameters, tuple):
            parameters = [parameters]

        c = self.conn.cursor()
        c.execute(sql, parameters)
        result = c.fetchone()

        return result



def sqlite_dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        dot = col[0].find('.') + 1
        if dot != -1:
            d[col[0][dot:]] = row[idx]
        else:
            d[col[0]] = row[idx]
    return d