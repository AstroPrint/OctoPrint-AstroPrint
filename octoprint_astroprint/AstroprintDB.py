# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2017 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import sqlite3

class AstroprintDB():

	def __init__(self, plugin):
		self.DB_NAME = plugin.get_plugin_data_folder() + "/octoprint_astroprint.db"
		conn = sqlite3.connect(self.DB_NAME)
		db = conn.cursor()

		db.execute('''CREATE TABLE IF NOT EXISTS user
		(
		id INT PRIMARY KEY NOT NULL DEFAULT(1),
		userId TEXT,
		name TEXT,
		email TEXT,
		token TEXT,
		refresh_token TEXT,
		accessKey TEXT,
		expires INTEGER,
		last_request INTEGER)''')

		db.execute('''CREATE TABLE IF NOT EXISTS printFile
		(
		printFileId TEXT,
		name TEXT,
		octoPrintPath TEXT,
		printFileName TEXT,
		renderedImage TEXT)''')

		conn.commit()
		conn.close()

	def dropDatabase(self):
		conn = sqlite3.connect(self.DB_NAME)
		db = conn.cursor()

		db.execute('''DROP TABLE IF EXISTS user''')
		db.execute('''DROP TABLE IF EXISTS printfile''')

		conn.commit()
		conn.close()


	def execute(self, sql):
		conn = sqlite3.connect(self.DB_NAME)
		db = conn.cursor()
		db.execute(sql)
		conn.commit()
		conn.close()

	def query(self, sql):
		conn = sqlite3.connect(self.DB_NAME)
		db = conn.cursor()
		db.execute(sql)
		return db.fetchall()

	def saveUser(self, user):
		sql = "INSERT INTO user (userId, name, email, token, refresh_token, accessKey, expires, last_request) VALUES ('%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s')" % (encrypt(user.userId), user.name, encrypt(user.email), encrypt(user.token), encrypt(user.refresh_token), encrypt(user.accessKey), user.expires, user.last_request)
		return self.execute(sql)

	def deleteUser(self, user):
		sql = "DELETE FROM user WHERE email = '%s'" % (encrypt(user.email))
		return self.execute(sql)

	def updateUser(self, user):
		sql = "UPDATE user SET userId= '%s', name = '%s', email = '%s', token = '%s', refresh_token = '%s', accessKey = '%s', expires = '%s', last_request = '%s' WHERE email = '%s'" % (encrypt(user.userId), user.name, encrypt(user.email), encrypt(user.token), encrypt(user.refresh_token), encrypt(user.accessKey), user.expires, user.last_request, encrypt(user.email),)
		return self.execute(sql)

	def getUser(self):
		conn = sqlite3.connect(self.DB_NAME)
		db = conn.cursor()
		sql = "SELECT * FROM user"
		db.execute(sql)
		user = db.fetchone()

		if user:
			return AstroprintUser(decrypt(user[1]), user[2] ,decrypt(user[3]), decrypt(user[4]), decrypt(user[5]), decrypt(user[6]), user[7], user[8])
		else:
			return None

	def savePrintFile(self, printFile):
		sql = "INSERT INTO printfile (printFileId, name, octoPrintPath, printFileName, renderedImage) VALUES ('%s', '%s', '%s', '%s', '%s')" % (printFile.printFileId, printFile.name, printFile.octoPrintPath, printFile.printFileName, printFile.renderedImage)
		return self.execute(sql)


	def deletePrintFile(self, path):
		sql = "DELETE FROM printfile WHERE octoPrintPath = '%s'" % (path)
		return self.execute(sql)

	def getPrintFileById(self, printFileId):
		conn = sqlite3.connect(self.DB_NAME)
		db = conn.cursor()
		sql = "SELECT * FROM printfile WHERE printFileId = '%s'" %printFileId
		db.execute(sql)
		printFile = db.fetchone()

		if printFile:
			return AstroprintPrintFile(printFile[0], printFile[1], printFile[2], printFile[3], printFile[4])
		else:
			return None

	def getPrintFileByOctoPrintPath(self, octoPrintPath):
		conn = sqlite3.connect(self.DB_NAME)
		db = conn.cursor()
		sql = "SELECT * FROM printfile WHERE octoPrintPath = '%s'" %octoPrintPath
		db.execute(sql)
		printFile = db.fetchone()

		if printFile:
			return AstroprintPrintFile(printFile[0], printFile[1], printFile[2], printFile[3], printFile[4])
		else:
			return None


class AstroprintUser():

	def __init__(self, userId="", name = "", email = "", token = "", refresh_token = "", accessKey= "", expires = 0, last_request = 0):
		self.userId = userId
		self.name = name
		self.email = email
		self.token = token
		self.refresh_token = refresh_token
		self.accessKey = accessKey
		self.expires = expires
		self.last_request = last_request

class AstroprintPrintFile():

	def __init__(self, printFileId = None, name="", octoPrintPath = "", printFileName="",  renderedImage = None):
		self.printFileId = printFileId
		self.name = name
		self.octoPrintPath = octoPrintPath
		self.printFileName = printFileName
		self.renderedImage = renderedImage

def encrypt(s):
    return s.encode('rot-13')

def decrypt(s):
    return s.encode('rot-13')
