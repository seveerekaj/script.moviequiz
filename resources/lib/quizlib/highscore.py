import mysql.connector
from mysql.connector import errorcode
import sqlite3
import xml.etree.ElementTree as ET
import hashlib
from datetime import datetime

import xbmc
import xbmcaddon
import xbmcvfs

from . import logger

class Database:
  def __init__(self):
    self.database = None
    self.type = None
    
  # Connect to a remote MySQL database if the file advancedsettings.xml is correctly filled
  #  or a local Sqlite database otherwise
  # self.database is set to None in case of error, a connection otherwise
  def connect(self):
    dbtype = None
    host = None
    user = None
    password = None
    
    try:
      fpath = xbmcvfs.translatePath('special://userdata/advancedsettings.xml')
      tree = ET.parse(fpath)
      root = tree.getroot()
      for videodatabase in root.iter('videodatabase'):
        for child in videodatabase:
          if child.tag == 'type':
            dbtype = child.text
          elif child.tag == 'host':
            host = child.text
          elif child.tag == 'user':
            user = child.text
          elif child.tag == 'pass':
            password = child.text
    except Exception as e:
      logger.log('Got exception {0} while trying to read advancedsettings.xml'.format(e))
      
    if dbtype == 'mysql' and host is not None and user is not None and password is not None:
      try:
        self.database = mysql.connector.connect(user=user, password=password, host=host)
        self.type = 'mysql'
      except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
          logger.log("Something is wrong with your user name or password", level=xbmc.LOGERROR)
        else:
          logger.log(err, level=xbmc.LOGERROR)
        self.database = None
   
    if self.database is None:
      # Use local sqlite
      addonId = xbmcaddon.Addon().getAddonInfo('id')
      fpath = xbmcvfs.translatePath('special://userdata/addon_data/{0}'.format(addonId))
      if not xbmcvfs.exists(fpath):
        xbmcvfs.mkdir(fpath)
      fpath = xbmcvfs.translatePath('special://userdata/addon_data/{0}/highscore.db'.format(addonId))
      try:
        self.database = sqlite3.connect(fpath)
        self.type = 'sqlite3'
      except Exception as e:
        logger.log('Got exception {0} while trying to connect to Sqlite database'.format(e), level=xbmc.LOGERROR)

  # Returns a string describing the connection type
  def getType(self):
    if self.type is None:
      return "No database connected"
    elif self.type == 'mysql':
      return "Connected on remote MySQL database"
    elif self.type == 'sqlite3':
      return "Connected on local Sqlite database"
    else:
      return "Unknown database"

  # Execute a SQL query
  # Return None in case of error, the result of the query otherwise
  def execute(self, query, database):
    # SELECT host FROM mysql.user WHERE User = 'root';
    if self.database is None:
      logger.log('No database connected', level=xbmc.LOGERROR)
      return None
      
    if self.type == 'mysql':
      try:
        cursor = self.database.cursor()
        if database is not None:
          try:
            cursor.execute("USE {}".format(database))
          except mysql.connector.Error as err:
            try:
              cursor.execute("CREATE DATABASE {} DEFAULT CHARACTER SET 'utf8'".format(database))
            except mysql.connector.Error as err:
              logger.log("Failed creating database: {}".format(err), level=xbmc.LOGERROR)
          self.database.database = database
        q = (query)
        cursor.execute(q)
        res = cursor.fetchall()
        cursor.close()
        self.database.commit()
        return res
      except Exception as e:
        logger.log('Got MySQL exception {0} while executing query {1}'.format(e, query), level=xbmc.LOGERROR)
        return None
    elif self.type == 'sqlite3':
      try:
        cur = self.database.cursor()
        res = cur.execute(query).fetchall()
        self.database.commit()
        return res
      except Exception as e:
        logger.log('Got Sqlite exception {0} while executing query {1}'.format(e, query), level=xbmc.LOGERROR)
        return None
    else:
      logger.log('Unknown database', level=xbmc.LOGERROR)
      return None

  # Close the database
  def close(self):
    if self.database is not None:
      self.database.close()

class User:
  def __init__(self):
    self.currentUser = None
    self.database = Database()
    if self.database is not None:
      self.database.connect()
      
  # Create a new user with name <name> and password <password>
  # Returns (True, 0) if successful, (False, error) otherwise
  def create(self, name, password):
    error = 0
    if self.database is not None:
      res = self.database.execute("SELECT name FROM users WHERE name = '{0}'".format(name), "users")
      if res is not None and len(res) > 0:
        logger.log('This user already exists. Please choose another name')
        error = 32025
      else:
        res = self.database.execute("CREATE TABLE IF NOT EXISTS users (name TEXT, password TEXT)", None)
        if res is not None:
          hashed = hashlib.sha256(password.encode('utf-8')).hexdigest()
          res = self.database.execute("INSERT INTO users VALUES ('{0}', '{1}')".format(name, hashed), "users")
          if res is None:
            logger.log('Failed to create user', level=xbmc.LOGERROR)
            error = 32026
          else:
            logger.log('User successfully created')
            return (True, 0)
        else:
          logger.log('Failed to create user', level=xbmc.LOGERROR)
          error = 32026
    else:
      logger.log('Cannot create user: no database connected', level=xbmc.LOGERROR)
      error = 32024
      
    return (False, error)
  
  # Removes the user with name <name> and password <password>
  # Returns (True, 0) if successful, (False, error) otherwise
  def remove(self, name, password):
    error = 0
    if self.database is not None:
      res = self.database.execute("SELECT name, password FROM users WHERE name = '{0}'".format(name), "users")
      if res is None or len(res) != 1:
        logger.log('This user does not exists')
        error = 32027
      else:
        hashed = hashlib.sha256(password.encode('utf-8')).hexdigest()
        if hashed != res[0][1]:
          logger.log('User not removed: invalid password')
          error = 32023
        else:
          res = self.database.execute("DELETE FROM highscores WHERE name = '{0}'".format(name), "highscores")
          res = self.database.execute("DELETE FROM users WHERE name = '{0}'".format(name), "users")
          if res is None:
            logger.log('Failed to remove user', level=xbmc.LOGERROR)
            error = 32028
          else:
            logger.log('User successfully removed')
            return (True, 0)
    else:
      logger.log('Cannot remove user: no database connected', level=xbmc.LOGERROR)
      error = 32024
      
    return (False, error)

  # Log the user with name <name> and password <password>
  # Returns (True, 0) if successful, (False, error) otherwise
  def login(self, name, password):
    error = 0
    if self.database is not None:
      res = self.database.execute("SELECT name, password FROM users WHERE name = '{0}'".format(name), "users")
      if res is None or len(res) != 1:
        logger.log('Login failed: no such user')
        error = 32022
      else:
        hashed = hashlib.sha256(password.encode('utf-8')).hexdigest()
        if hashed != res[0][1]:
          logger.log('Login failed: invalid password')
          error = 32023
        else:
          logger.log('User successfully logged')
          self.currentUser = name
          return (True, 0)
    else:
      logger.log('Login failed: no database connected', level=xbmc.LOGERROR)
      error = 32024
      
    return (False, error)
  
  # Logout the user
  def logout(self):
    self.currentUser = None
    
  # Clean-up the instance
  def close(self):
    if self.database is not None:
      self.database.close()

class Highscore:
  def __init__(self):
    self.currentRoundLength = None
    self.database = Database()
    if self.database is not None:
      self.database.connect()
      
  # Add a highscore in the database
  # Returns True in case of success, False otherwise
  def add(self, name, roundLength, nbCorrectAnswers, gameType):
    if self.database is not None:
      res = self.database.execute("CREATE TABLE IF NOT EXISTS highscores (name TEXT, score INTEGER, length INTEGER, date TEXT, type TEXT)", "highscores")
      if res is not None:
        now = datetime.now()
        formatted_date = now.strftime('%Y-%m-%d %H:%M')
        res = self.database.execute("INSERT INTO highscores VALUES ('{0}', {1}, {2}, '{3}', '{4}')".format(name, nbCorrectAnswers, roundLength, formatted_date, gameType), "highscores")
        if res is None:
          logger.log('Failed to add highscore', level=xbmc.LOGERROR)
        else:
          logger.log('Highscore successfully added')
          return True
      else:
        logger.log('Failed to add the highscore', level=xbmc.LOGERROR)
    else:
      logger.log('Cannot add the highscore: no database connected', level=xbmc.LOGERROR)
      
    return False

  # Returns the list of highscores corresponding to a certain round length
  def list(self, roundLength, gameType):
    if self.database is not None:
      return self.database.execute("SELECT name, score, date, type FROM highscores WHERE length = {0} AND type = '{1}' ORDER BY score DESC, date DESC LIMIT 100".format(roundLength, gameType), "highscores")
    else:
      logger.log('Cannot list the highscores: no database connected', level=xbmc.LOGERROR)
      return []
  
  # Clean-up the instance
  def close(self):
    if self.database is not None:
      self.database.close()
