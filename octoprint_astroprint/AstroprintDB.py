# coding=utf-8
from __future__ import absolute_import,   unicode_literals

__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2017-2020 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import os
import yaml
import copy
import codecs

class AstroprintDB():

	def __init__(self, plugin):
		dataFolder = plugin.get_plugin_data_folder()

		self.plugin = plugin
		self._logger = plugin.get_logger()
		self.infoPrintFiles = os.path.join(dataFolder,"print_files.yaml")
		self.printFiles = {}
		self.getPrintFiles()

		self.infoUser = os.path.join(dataFolder,"user.yaml")
		self.user = None
		self.getUser()

	def saveUser(self, user):
		# Copy the user object as we need the member unencrypted and the encryption operation below will modify the original object
		self.user = copy.copy(user)
		if user:
			user['email'] = encrypt(user['email']) if user['email'] else None
			user['accessKey'] = encrypt(user['accessKey'])
			user['orgId'] = encrypt(user['orgId']) if user['orgId'] else None
			user['groupId'] = encrypt(user['groupId']) if user['groupId'] else None

		with open(self.infoUser, "w") as infoFile:
			yaml.safe_dump({"user" : user}, infoFile, default_flow_style=False, indent=4, allow_unicode=True)

		self.plugin.user = self.user

	def getUser(self):
		try:
			with open(self.infoUser, "r") as f:
				user = yaml.safe_load(f)
				if user and user['user']:
					orgId = None
					groupId = None
					if 'orgId' in user:
						orgId = user['orgId']
					if 'groupId' in user:
						groupId = user['groupId']
					self.user = user['user']
					self.user['email'] = decrypt(self.user['email'])
					self.user['accessKey'] = decrypt(self.user['accessKey'])
					self.user['orgId'] = decrypt(orgId) if orgId else None
					self.user['groupId'] = decrypt(groupId) if groupId else None

		except IOError as e:
			if e.errno == 2:
				self._logger.info("No user yaml: %s" % self.infoUser)
			else:
				self._logger.error("IOError error loading %s" % self.infoUser, exc_info= True)

		except:
			self._logger.error("There was an error loading %s" % self.infoUser, exc_info= True)

		self.plugin.user = self.user

	def deleteUser(self):
		self.saveUser(None)

	def getPrintFiles(self):
		try:
			with open(self.infoPrintFiles, "r") as f:
				printFiles = yaml.safe_load(f)
				if printFiles:
					self.printFiles = printFiles

		except IOError as e:
			if e.errno == 2:
				self._logger.info("No print files yaml: %s" % self.infoPrintFiles)
			else:
				self._logger.error("IOError error loading %s" % self.infoPrintFiles, exc_info= True)

		except:
			self._logger.info("There was an error loading %s" % self.infoPrintFiles, exc_info= True)

		self.plugin.printFiles = self.printFiles

	def savePrintFiles(self, printFiles):
		self.printFiles = printFiles
		with open(self.infoPrintFiles, "w") as infoFile:
			yaml.safe_dump(printFiles, infoFile, default_flow_style=False, indent=4, allow_unicode=True)
		self.plugin.printFiles = self.printFiles

	def savePrintFile(self, printFile):
		self.printFiles[printFile.printFileId] = {"name" : printFile.name, "octoPrintPath" : printFile.octoPrintPath, "printFileName" : printFile.printFileName, "renderedImage" : printFile.renderedImage}
		self.savePrintFiles(self.printFiles)

	def deletePrintFile(self, path):
		printFiles = {}
		if self.printFiles:
			for printFile in self.printFiles:
				if self.printFiles[printFile]["octoPrintPath"] != path:
					printFiles[printFile] = self.printFiles[printFile]
			self.savePrintFiles(printFiles)

	def getPrintFileById(self, printFileId):
		if self.printFiles and printFileId in self.printFiles:
			return 	AstroprintPrintFile(printFileId, self.printFiles[printFileId]["name"], self.printFiles[printFileId]["octoPrintPath"], self.printFiles[printFileId]["printFileName"], self.printFiles[printFileId]["renderedImage"])
		return None


	def getPrintFileByOctoPrintPath(self, octoPrintPath):
		if self.printFiles:
			for printFile in self.printFiles:
				if self.printFiles[printFile]["octoPrintPath"] == octoPrintPath:
					return AstroprintPrintFile(printFile, self.printFiles[printFile]["name"], self.printFiles[printFile]["octoPrintPath"], self.printFiles[printFile]["printFileName"], self.printFiles[printFile]["renderedImage"])
		return None

class AstroprintPrintFile():

	def __init__(self, printFileId = None, name="", octoPrintPath = "", printFileName="",  renderedImage = None):
		self.printFileId = printFileId
		self.name = name
		self.octoPrintPath = octoPrintPath
		self.printFileName = printFileName
		self.renderedImage = renderedImage

def encrypt(s):
    return codecs.encode(s, 'rot-13')

def decrypt(s):
    return codecs.encode(s, 'rot-13')
