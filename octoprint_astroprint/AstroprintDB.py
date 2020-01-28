# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2017-2019 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import os
import yaml
import copy

class AstroprintDB():

	def __init__(self, plugin):
		self.plugin = plugin
		self._logger = plugin.get_logger()
		self.infoPrintFiles = plugin.get_plugin_data_folder() + "/print_files.yaml"
		self.printFiles = {}
		self.getPrintFiles()

		self.infoUser = plugin.get_plugin_data_folder() + "/user.yaml"
		self.user = {}
		self.getUser()

		self.infoGroupId = plugin.get_plugin_data_folder() + "/info_group.yaml"
		self.groupId = None
		self.getGroupId()

	def saveUser(self, user):
		self.user = copy.copy(user)
		if user:
			user['email'] = encrypt(user['email'])
			user['accessKey'] = encrypt(user['accessKey'])
		with open(self.infoUser, "wb") as infoFile:
			yaml.safe_dump({"user" : user}, infoFile, default_flow_style=False, indent="    ", allow_unicode=True)
		self.plugin.user = self.user

	def saveGroupId(self, groupId):
		self.groupId = groupId
		if groupId:
			groupId = encrypt(groupId)
		with open(self.infoGroupId, "wb") as infoFile:
			yaml.safe_dump({"groupId" : groupId}, infoFile, default_flow_style=False, indent="    ", allow_unicode=True)
		self.plugin.groupId = self.groupId

	def getUser(self):
		try:
			with open(self.infoUser, "r") as f:
				user = yaml.safe_load(f)
				if user and user['user']:
					self.user = user['user']
					self.user['email'] = decrypt(self.user['email'])
					self.user['accessKey'] = decrypt(self.user['accessKey'])

		except IOError, e:
			if e.errno == 2:
				self._logger.warn("No user yaml found")
			else:
				self._logger.error("IOError error loading %s:" % self.infoUser, exc_info= True)

		except:
			self._logger.error("There was an error loading %s:" % self.infoUser, exc_info= True)

		self.plugin.user = self.user

	def getGroupId(self):
		try:
			with open(self.infoGroupId, "r") as f:
				infoGroup = yaml.safe_load(f)
				if infoGroup and infoGroup['groupId']:
					self.groupId = decrypt(infoGroup['groupId'])

		except IOError, e:
			if e.errno == 2:
				self._logger.warn("No group info yaml found")
			else:
				self._logger.error("IOError error loading %s:" % self.groupId, exc_info= True)

		except:
			self._logger.error("There was an error loading %s:" % self.groupId, exc_info= True)

		self.plugin.groupId = self.groupId

	def deleteUser(self):
		self.saveUser(None)

	def deleteGroupId(self):
		self.saveGroupId(None)

	def getPrintFiles(self):
		try:
			with open(self.infoPrintFiles, "r") as f:
				printFiles = yaml.safe_load(f)
				if printFiles:
					self.printFiles = printFiles

		except IOError, e:
			if e.errno == 2:
				self._logger.warn("No print files yaml found")
			else:
				self._logger.error("IOError error loading %s:" % self.infoPrintFiles, exc_info= True)

		except:
			self._logger.info("There was an error loading %s:" % self.infoPrintFiles, exc_info= True)

		self.plugin.printFiles = self.printFiles

	def savePrintFiles(self, printFiles):
		self.printFiles = printFiles
		with open(self.infoPrintFiles, "wb") as infoFile:
			yaml.safe_dump(printFiles, infoFile, default_flow_style=False, indent="    ", allow_unicode=True)
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
    return s.encode('rot-13')

def decrypt(s):
    return s.encode('rot-13')
