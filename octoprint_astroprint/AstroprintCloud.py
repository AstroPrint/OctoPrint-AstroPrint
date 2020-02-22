# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2017-2019 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

from flask import request, make_response, jsonify
import time
import json
import octoprint.filemanager
from .downloadmanager import DownloadManager
from .boxrouter import boxrouterManager
from requests_toolbelt import MultipartEncoder
import requests
import os
import octoprint.filemanager.util
from octoprint.filemanager.destinations import FileDestinations
from octoprint.server import VERSION
from threading import Lock
import sys
import platform

class AstroprintCloud():

	def __init__(self, plugin):
		self.plugin = None
		self.appId = None
		self.currentPrintingJob = None
		self.getTokenRefreshLock = Lock()

		self.plugin = plugin
		self.boxId = self.plugin.boxId
		self.apiHost = plugin.get_settings().get(["apiHost"])
		self.appId = plugin.get_settings().get(["appId"])
		self.db = self.plugin.db
		self.bm = boxrouterManager(self.plugin)
		self.downloadmanager = DownloadManager(self)
		self._logger = self.plugin.get_logger()
		self._printer = plugin.get_printer()
		self._file_manager = plugin.get_file_manager()
		self.plugin.cameraManager.astroprintCloud = self
		self.plugin.get_printer_listener().astroprintCloud = self
		self.statePayload = None
		self.printJobData = None
		user = self.plugin.user
		if user:
			self._logger.info("Found stored AstroPrint User [%s]" % user['name'])
			self.getUserInfo()
			self.getFleetInfo()
		else:
			self._logger.info("No stored AstroPrint user")


	def tokenIsExpired(self):
		return (self.plugin.user['expires'] - int(time.time()) < 60)

	def getToken(self):
		if self.tokenIsExpired():
			with self.getTokenRefreshLock:
				# We need to check again because there could be calls that were waiting on the lock for an active refresh.
				# These calls should not have to refresh again as the token would be valid
				if self.tokenIsExpired():
					self.refresh()

			return self.getToken()

		else:
			return self.plugin.user['token']

	def getTokenRequestHeaders(self, contentType = 'application/x-www-form-urlencoded'):
		token = self.getToken()
		headers = {
				'Content-Type': contentType,
				'authorization': "bearer %s" % token
			}
		if(self.plugin.user['groupId']):
			headers['X-Org-Id'] = self.plugin.user['orgId']
			headers['X-Group-Id'] = self.plugin.user['groupId']

		return headers

	def refresh(self):
		try:
			r = requests.post(
				"%s/token" % (self.apiHost),
				data = {
					"client_id": self.appId,
					"grant_type": "refresh_token",
					"refresh_token": self.plugin.user['refresh_token']
					},
			)
			r.raise_for_status()
			data = r.json()
			self.plugin.user['token'] = data['access_token']
			self.plugin.user['refresh_token'] = data['refresh_token']
			self.plugin.user['last_request'] = int(time.time())
			self.plugin.user['expires'] = self.plugin.user['last_request'] + data['expires_in']
			self.db.saveUser(self.plugin.user)

		except requests.exceptions.HTTPError as err:
			if err.response.status_code == 400 or err.response.status_code == 401:
				self._logger.error("Unable to refresh token with error [%d]" % err.response.status_code)
				self.plugin.send_event("logOut")
				self.unauthorizedHandler()

		except requests.exceptions.RequestException as e:
			self._logger.error(e, exc_info=True)

	def loginAstroPrint(self, code, url, apAccessKey, boxId = None):
		self._logger.info("Logging into AstroPrint with boxId: %s" % boxId)
		try:
			r = requests.post(
				"%s/token" % (self.apiHost),
				data = {
					"client_id": self.appId,
					"access_key" : apAccessKey,
					"grant_type": "controller_authorization_code",
					"code": code,
					"redirect_uri": url,
					"box_id" : boxId
					},
			)
			r.raise_for_status()
			data = r.json()
			self.plugin.user = {}
			self.plugin.user['token'] = data['access_token']
			self.plugin.user['refresh_token'] = data['refresh_token']
			self.plugin.user['last_request'] = int(time.time())
			self.plugin.user['accessKey'] = apAccessKey
			self.plugin.user['expires'] = self.plugin.user['last_request'] + data['expires_in']
			self.plugin.user['email'] = None
			self.plugin.user['orgId'] = None
			self.plugin.user['groupId'] = None
			self.getFleetInfo()
			return self.getUserInfo(True)

		except requests.exceptions.HTTPError as err:
			self._logger.error("Error while logging into AstroPrint: %s" % err.response.text)
			return jsonify(json.loads(err.response.text)), err.response.status_code, {'ContentType':'application/json'}
		except requests.exceptions.RequestException as e:
			self._logger.error(e, exc_info=True)
			return jsonify({'error': "Internal server error"}), 500, {'ContentType':'application/json'}

	def getUserInfo(self, saveUser = False):
		self._logger.info("Getting AstroPrint user info")
		try:
			tokenHeaders = self.getTokenRequestHeaders('application/x-www-form-urlencoded')
			r = requests.get(
				"%s/accounts/me" % (self.apiHost),
				headers = tokenHeaders
			)
			r.raise_for_status()
			data = r.json()
			self.plugin.user['id'] = data['id']
			self.plugin.user['email'] = data['email']
			self.plugin.user['name'] = data['name']
			self.plugin.sendSocketInfo()
			if saveUser:
				self.db.saveUser(self.plugin.user)
				self._logger.info("AstroPrint User [%s] logged in and saved" % self.plugin.user['name'])
				self.connectBoxrouter()
				return jsonify({'name': self.plugin.user['name'], 'email': self.plugin.user['email']}), 200, {'ContentType':'application/json'}

		except requests.exceptions.HTTPError as err:
			if (err.response.status_code == 401):
				self.unauthorizedHandler()
			if saveUser:
				return jsonify(json.loads(err.response.text)), err.response.status_code, {'ContentType':'application/json'}
		except requests.exceptions.RequestException:
			if saveUser:
				return jsonify({'error': "Internal server error"}), 500, {'ContentType':'application/json'}

	def getFleetInfo(self):
		try:
			tokenHeaders = self.getTokenRequestHeaders('application/x-www-form-urlencoded')
			r = requests.get(
				"%s/devices/%s/fleet" % (self.apiHost, self.boxId),
				headers = tokenHeaders
			)
			r.raise_for_status()
			data = r.json()
			if self.plugin.user['groupId'] != data['group_id']:
				self._logger.info("Box group id updated")
				self.plugin.user['orgId'] = data['organization_id']
				self.plugin.user['groupId'] =  data['group_id']
				self.db.saveUser(self.plugin.user)

		except requests.exceptions.HTTPError as err:
			if (err.response.status_code == 401 or (err.response.status_code == 404 and self.plugin.user['groupId'])):
				self._logger.info("Box is in a fleet group where user does not has permission, logout")
				self.unauthorizedHandler()
			else:
				self._logger.error("getFleetInfo failed with error %d" % err.response.status_code)

		except requests.exceptions.RequestException as e:
			self._logger.error(e, exc_info=True)

	def updateFleetInfo(self, orgId, groupId):
		if self.plugin.user['groupId'] != groupId:
			self.plugin.user['orgId'] = orgId
			self.plugin.user['groupId'] = groupId


	def logoutAstroPrint(self):
		self.unauthorizedHandler(False)
		return jsonify({"Success" : True }), 200, {'ContentType':'application/json'}

	def unauthorizedHandler (self, expired = True):
		if(expired):
			self._logger.warning("Unautorized token, AstroPrint user logged out.")
		self.db.deleteUser()
		self.currentPrintingJob = None
		self.disconnectBoxrouter()
		self.plugin.astroPrintUserLoggedOut()

	def printStarted(self, name, path):

		print_file = self.db.getPrintFileByOctoPrintPath(path)
		print_file_id = print_file.printFileId if print_file else None
		print_file_name = print_file.printFileName if print_file else name

		if self.printJobData:
			if self.printJobData['print_file'] == print_file_id:
				self.currentPrintingJob = self.printJobData['print_job_id']
				self.updatePrintJob("started")
			else:
				self.printJobData = None
				self.startPrintJob(print_file_id, print_file_name)
		else:
			self.startPrintJob(print_file_id, print_file_name)

	def startPrintJob(self, print_file_id= None, print_file_name= None):
		try:
			tokenHeaders = self.getTokenRequestHeaders('application/x-www-form-urlencoded')
			data = {
					"box_id": self.plugin.boxId,
					"product_variant_id": self.plugin.get_settings().get(["product_variant_id"]),
					"name": print_file_name,
					}

			if print_file_id:
				data['print_file_id'] = print_file_id


			r = requests.post(
				"%s/print-jobs" % (self.apiHost),
				json = data,
				headers = tokenHeaders,
				stream=True
			)

			data = r.json()
			self.currentPrintingJob = data['id']

		except requests.exceptions.HTTPError as err:
			if (err.response.status_code == 401):
				self.unauthorizedHandler()
			self._logger.error("Failed to send print_job request: %s" % err.response.text)
		except requests.exceptions.RequestException as e:
			self._logger.error("Failed to send print_job request: %s" % e)

	def updatePrintJob(self, status, totalConsumedFilament = None):
		try:
			tokenHeaders = self.getTokenRequestHeaders('application/x-www-form-urlencoded')
			data = {'status': status}

			if totalConsumedFilament:
				data['material_used'] = totalConsumedFilament

			requests.patch(
				"%s/print-jobs/%s" % (self.apiHost, self.currentPrintingJob),
				json = data,
				headers = tokenHeaders,
				stream=True
			)

		except requests.exceptions.HTTPError as err:
			if (err.response.status_code == 401):
				self.unauthorizedHandler()
			self._logger.error("Failed to send print_job request: %s" % err.response.text)
		except requests.exceptions.RequestException as e:
			self._logger.error("Failed to send print_job request: %s" % e)

	def connectBoxrouter(self):
		if self.plugin.user and "accessKey" in self.plugin.user and "id" in self.plugin.user:
			self._logger.info("Connecting Box Router")
			self.bm.boxrouter_connect()
			#let the singleton be recreated again, so new credentials are taken into use
			global _instance
			_instance = None
			return True

		return False

	def disconnectBoxrouter(self):
		self.bm.boxrouter_disconnect()

	def sendCurrentData(self):

		payload = {
			'operational': self.plugin.get_printer().is_operational(),
			'printing': self.plugin.get_printer().is_paused() or self.plugin._printer.is_printing(),
			'paused': self.plugin.get_printer().is_paused(),
			'camera': True, #self.plugin.cameraManager.cameraActive
			'heatingUp': self.plugin.printerIsHeating(),
			'tool' : self.plugin.currentTool()
		}

		if self.statePayload != payload and self.bm:
			self.bm.broadcastEvent('status_update', payload)
			self.statePayload = payload


	def printFile(self, printFileId, printJobData = None, printNow = False):
		printFile = self.db.getPrintFileById(printFileId)
		if printNow:
			self.printJobData = printJobData
		if printFile and printNow:
			self.printFileIsDownloaded(printFile)
			return "print"
		else:
			printFile = self.addPrintfileDownloadUrl(self.getPrintFileInfoForDownload(printFileId))
			if printFile:
				printFile['printNow'] = printNow
				if not self.downloadmanager.isDownloading(printFileId):
					self.downloadmanager.startDownload(printFile)
				return "download"
			return None

	def getPrintFileInfoForDownload(self, printFileId):
		self._currentDownlading = printFileId
		self._downloading= True
		try:
			tokenHeaders = self.getTokenRequestHeaders()
			r = requests.get(
				"%s/printfiles/%s" % (self.apiHost, printFileId),
				headers= tokenHeaders,
				stream=True
			)
			r.raise_for_status()
			printFile = r.json()
			if printFile['format'] == 'gcode' :
				return printFile
			else:
				payload = {
					"id" : printFileId,
					"type" : "error",
					"reason" : "Invalid file extension"
				}
				self.bm.triggerEvent('onDownload', payload)

		except requests.exceptions.HTTPError as err:
			payload = {
				"id" :printFileId,
				"type" : "error",
				"reason" : err.response.text
			}
			self.bm.triggerEvent('onDownload', payload)
			if (err.response.status_code == 401):
				self.unauthorizedHandler()
			return None
		except requests.exceptions.RequestException:
			payload = {
				"id" : printFile['id'],
				"type" : "error",
			}
			self.bm.triggerEvent('onDownload', payload)
			return None

	def addPrintfileDownloadUrl(self, printFile):
		if not printFile:
			return None
		try:
			tokenHeaders = self.getTokenRequestHeaders()
			r = requests.get(
				"%s/printfiles/%s/download?download_info=true" % (self.apiHost, printFile['id']),
				headers = tokenHeaders,
				stream=True
			)
			r.raise_for_status()
			downloadInfo = r.json()
			printFile['download_url'] = downloadInfo['download_url']

			return printFile

		except requests.exceptions.HTTPError as err:

			payload = {
				"id" : printFile['id'],
				"type" : "error",
				"reason" : err.response.text
			}
			self.bm.triggerEvent('onDownload', payload)
			if (err.response.status_code == 401):
				self.unauthorizedHandler()
			return None
		except requests.exceptions.RequestException:

			payload = {
				"id" : printFile['id'],
				"type" : "error",
			}

			self.bm.triggerEvent('onDownload', payload)
			return None


	def wrapAndSave(self, fileType, file, printNow=False):
		name = file if fileType == "design" else file.printFileName
		filepath = ("%s/%s" %(self.plugin._basefolder, name))
		fileObject = octoprint.filemanager.util.DiskFileWrapper(name, filepath)

		try:
			self._file_manager.add_file(FileDestinations.LOCAL, name, fileObject, allow_overwrite=True)
			if fileType == "printFile":
				self.db.savePrintFile(file)
				if printNow:
					self.printFileIsDownloaded(file)
			return None

		except octoprint.filemanager.storage.StorageError as e:
			if os.path.exists(filepath):
				os.remove(filepath)
				if e.code == octoprint.filemanager.storage.StorageError.INVALID_FILE:
					payload = {
						"id" : file.printFileId,
						"type" : "error",
						"reason" : e.code
					}
					self.bm.triggerEvent('onDownload', payload)
					return None
				elif e.code == octoprint.filemanager.storage.StorageError.ALREADY_EXISTS:
					payload = {
						"id" : file.printFileId,
						"type" : "error",
						"reason" : e.code
					}
					self.bm.triggerEvent('onDownload', payload)
					return None
				else:
					payload = {
						"id" : file.printFileId,
						"type" : "error",
					}
					self.bm.triggerEvent('onDownload', payload)
					return None
			else:
				return None

	def printFileIsDownloaded(self, printFile):
		if self._printer.is_printing():
			isBeingPrinted = False
			self.printJobData = None
		else:
			self._printer.select_file(self._file_manager.path_on_disk(FileDestinations.LOCAL, printFile.printFileName), False, True)
			if self._printer.is_printing():
				isBeingPrinted = True
			else:
				isBeingPrinted = False
				self.printJobData = None
		self.bm.triggerEvent('onDownloadComplete', {"id": printFile.printFileId, "isBeingPrinted": isBeingPrinted})

	def getDesigns(self):
		try:
			tokenHeaders = self.getTokenRequestHeaders()
			r = requests.get(
				"%s/designs" % (self.apiHost),
				headers = tokenHeaders
			)
			r.raise_for_status()
			data = r.json()
			return jsonify(data), 200, {'ContentType':'application/json'}

		except requests.exceptions.HTTPError as err:
			if (err.response.status_code == 401):
				self.unauthorizedHandler()
			return jsonify({'error': "Unauthorized user"}), err.response.status_code, {'ContentType':'application/json'}
		except requests.exceptions.RequestException:
			return jsonify({'error': "Internal server error"}), 500, {'ContentType':'application/json'}

	def getDesignDownloadUrl(self, designId, name):
		try:
			tokenHeaders = self.getTokenRequestHeaders()
			r = requests.get(
				"%s/designs/%s/download" % (self.apiHost, designId),
				headers = tokenHeaders
			)
			r.raise_for_status()
			data = r.json()

			self.downloadmanager.startDownload({"id": designId, "name" : name, "download_url" : data['download_url'], "designDownload" : True, "printNow" : False})
			return jsonify({"Success" : True }), 200, {'ContentType':'application/json'}
		except requests.exceptions.HTTPError as err:
			if (err.response.status_code == 401):
				self.unauthorizedHandler()
			return jsonify({'error': "Unauthorized user"}), err.response.status_code, {'ContentType':'application/json'}
		except requests.exceptions.RequestException:
			return jsonify({'error': "Internal server error"}), 500, {'ContentType':'application/json'}

	def getPrintFiles(self, designId):
		tokenHeaders = self.getTokenRequestHeaders()
		if designId:
			try:
				r = requests.get(
					"%s/designs/%s/printfiles" % (self.apiHost, designId),
					headers = tokenHeaders
				)
				r.raise_for_status()
				data = r.json()
				return jsonify(data), 200, {'ContentType':'application/json'}

			except requests.exceptions.HTTPError as err:
				if (err.response.status_code == 401):
					self.unauthorizedHandler()
				return jsonify({'error': "Unauthorized user"}), err.response.status_code, {'ContentType':'application/json'}
			except requests.exceptions.RequestException:
				return jsonify({'error': "Internal server error"}), 500, {'ContentType':'application/json'}
		else:
			try:
				r = requests.get(
					"%s/printfiles?design_id=null" % (self.apiHost),
					headers = tokenHeaders
				)
				r.raise_for_status()
				data = r.json()
				return jsonify(data), 200, {'ContentType':'application/json'}

			except requests.exceptions.HTTPError as err:
				if (err.response.status_code == 401):
					self.unauthorizedHandler()
				return jsonify({'error': "Unauthorized user"}), err.response.status_code, {'ContentType':'application/json'}
			except requests.exceptions.RequestException:
				return jsonify({'error': "Internal server error"}), 500, {'ContentType':'application/json'}

	def cancelDownload(self, printFileId):
		self.downloadmanager.cancelDownload(printFileId)


	def startPrintCapture(self, filename, filepath):
		data = {'name': filename}

		astroprint_print_file = self.db.getPrintFileByOctoPrintPath(filepath)

		if astroprint_print_file:
			data['print_file_id'] = astroprint_print_file.printFileId

		if self.currentPrintingJob:
			data['print_job_id'] = self.currentPrintingJob

		try:
			tokenHeaders = self.getTokenRequestHeaders()
			r = requests.post(
				"%s/timelapse" % self.apiHost,
				headers = tokenHeaders,
				stream=True, timeout= (10.0, 60.0),
				data = data
			)

			status_code = r.status_code

		except:
			status_code = 500

		if status_code == 201:
			data = r.json()
			return {
				"error": False,
				"print_id": data['print_id']
			}

		if status_code == 402:
			return {
				"error": "no_storage"
			}

		else:
			return {
				"error": "unable_to_create"
			}

	def uploadImageFile(self, print_id, imageBuf):
			try:
				m = MultipartEncoder(fields=[('file',('snapshot.jpg', imageBuf))])
				tokenHeaders = self.getTokenRequestHeaders(m.content_type)
				r = requests.post(
					"%s/timelapse/%s/image" % (self.apiHost, print_id),
					data= m,
					headers= tokenHeaders
				)
				m = None #Free the memory?
				status_code = r.status_code

			except requests.exceptions.HTTPError:
				status_code = 500
			except requests.exceptions.RequestException:
				status_code = 500

			if status_code == 201:
				data = r.json()
				return data
			else:
				return None

	def getManufacturer(self):
		try:
			r = requests.get(
				"%s/manufacturers" % (self.apiHost),
				headers={'Content-Type': 'application/x-www-form-urlencoded' }
			)
			r.raise_for_status()
			data = r.json()
			return jsonify(data), 200, {'ContentType':'application/json'}

		except requests.exceptions.HTTPError as err:
			if (err.response.status_code == 401):
				self.unauthorizedHandler()
			return jsonify({'error': "Unauthorized user"}), err.response.status_code, {'ContentType':'application/json'}
		except requests.exceptions.RequestException:

			return jsonify({'error': "Internal server error"}), 500, {'ContentType':'application/json'}

	def getManufacturerModels(self, manufacturer_id):
		try:
			r = requests.get(
				"%s/manufacturers/%s/models?format=gcode" % (self.apiHost, manufacturer_id),
				headers={'Content-Type': 'application/x-www-form-urlencoded' }
			)
			r.raise_for_status()
			data = r.json()
			return jsonify(data), 200, {'ContentType':'application/json'}

		except requests.exceptions.HTTPError as err:
			if (err.response.status_code == 401):
				self.unauthorizedHandler()
			return jsonify({'error': "Unauthorized user"}), err.response.status_code, {'ContentType':'application/json'}
		except requests.exceptions.RequestException:
			return jsonify({'error': "Internal server error"}), 500, {'ContentType':'application/json'}

	def getModelInfo(self, model_id):
		try:
			r = requests.get(
				"%s/manufacturers/models/%s" % (self.apiHost, model_id),
				headers={'Content-Type': 'application/x-www-form-urlencoded' }
			)
			r.raise_for_status()
			data = r.json()
			return jsonify(data), 200, {'ContentType':'application/json'}

		except requests.exceptions.HTTPError as err:
			if (err.response.status_code == 401):
				self.unauthorizedHandler()
			return jsonify({'error': "Unauthorized user"}), err.response.status_code, {'ContentType':'application/json'}
		except requests.exceptions.RequestException:
			return jsonify({'error': "Internal server error"}), 500, {'ContentType':'application/json'}

	def updateBoxrouterData(self, data):
		try:

			tokenHeaders = self.getTokenRequestHeaders('application/json')

			r = requests.patch(
				"%s/devices/%s/update-boxrouter-data" % (self.apiHost, self.plugin.boxId),
				headers = tokenHeaders,
				data=json.dumps(data)
			)

			r.raise_for_status()

			return jsonify({'success': "Device Updated"}), 200, {'ContentType':'application/json'}

		except requests.exceptions.HTTPError as err:
			if (err.response.status_code == 401):
				self.unauthorizedHandler()
			return jsonify({'error': "Unauthorized user"}), err.response.status_code, {'ContentType':'application/json'}
		except requests.exceptions.RequestException:
			return jsonify({'error': "Internal server error"}), 500, {'ContentType':'application/json'}
