# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2017-2019 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import sqlite3
#KEEP FOR MIGRATION, IT WILL BE REMOVED AFTER SOME VERSIONS
class SqliteDB():

	def __init__(self, plugin):
		self.DB_NAME = plugin.get_plugin_data_folder() + "/octoprint_astroprint.db"

	def execute(self, sql):
		conn = sqlite3.connect(self.DB_NAME)
		db = conn.cursor()
		db.execute(sql)
		conn.commit()
		conn.close()

	def getUser(self):
		conn = sqlite3.connect(self.DB_NAME)
		db = conn.cursor()
		sql = "SELECT * FROM user"
		db.execute(sql)
		user = db.fetchone()
		userData = {}

		if user:
			userData = {"name" : user[2], "email" : decrypt(user[3]) ,"token" : decrypt(user[4]), "refresh_token" : decrypt(user[5]), "accessKey" : decrypt(user[6]), "expires" : user[7], "last_request" : user[8]}
		else:
			userData = None
		return userData

	def getPrintFiles(self):
		conn = sqlite3.connect(self.DB_NAME)
		db = conn.cursor()
		sql = "SELECT * FROM printfile"
		db.execute(sql)
		printFiles = db.fetchall()
		allPrintFiles = {}
		for printFile in printFiles:
			allPrintFiles[printFile[0]] = {"name" : printFile[1], "octoPrintPath" : printFile[2], "printFileName" : printFile[3], "renderedImage" : printFile[4]}
		return allPrintFiles

def decrypt(s):
    return s.encode('rot-13')
