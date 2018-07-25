# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2017 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

from flask import request
import requests
import threading
import os
from octoprint_astroprint.AstroprintDB import AstroprintPrintFile
from Queue import Queue

class DownloadWorker(threading.Thread):

	def __init__(self, manager):
		self._daemon = True
		self._manager = manager
		self._activeRequest = None
		self._canceled = False
		self.activeDownload = False
		self.plugin = manager.plugin
		self._logger = manager.plugin.get_logger()
		self.astroprintCloud = manager.astroprintCloud
		self.db = manager.astroprintCloud.db
		self.bm = manager.astroprintCloud.bm
		super(DownloadWorker, self).__init__()

	def run(self):
		downloadQueue = self._manager.queue

		while True:

			item = downloadQueue.get()
			if item == 'shutdown':
				return

			id = item['id']
			name = item['name']
			fileName = name
			url = image = item['download_url']
			destination = None
			printFile = False
			if not 'designDownload' in item:
				printFile = True
			if printFile:

				fileName = item['filename']
				substr = ".gcode"
				idx = fileName.index(substr)
				fileName = fileName[:idx] + id + fileName[idx:]
				image = item['design']['images']['square'] if item['design'] else None


			self.activeDownload = id

			self._logger.info("Downloading %s" % fileName)

			try:

				r = requests.get(
					url,
					stream=True,
					timeout= (10.0, 60.0)
				)

				if r.status_code == 200:
					content_length = float(r.headers.get('content-length'))
					downloaded_size = 0.0
					destination = "%s/%s" %(self.plugin._basefolder, fileName)
					with open(destination, 'wb') as file:
						for chunk in r.iter_content(100000): #download 100kb at a time
							downloaded_size += len(chunk)
							file.write(chunk)
							progress = 2 + round((downloaded_size / content_length) * 98.0, 1)
							if printFile:
								payload = {
									"id" : id,
									"progress" : progress,
									"type" : "progress",
								}
								self.bm.triggerEvent('onDownload', payload)
							self.plugin.send_event("download", {'id' : id, 'name': fileName, 'progress' : progress})

							if self._canceled: #check again before going to read next chunk
								break

				r.raise_for_status()

				if self._canceled:
							self._manager._logger.warn('Download canceled for %s' % id)
							self.clearFile(destination)
							self.downloadCanceled(id, fileName)
				else:
					if printFile:
						pf = AstroprintPrintFile(id, name, fileName, fileName, image)
						self.astroprintCloud.wrapAndSave("printFile", pf, True)
					else:
						self.astroprintCloud.wrapAndSave("design", name, False)

			except requests.exceptions.HTTPError as err:
				self._logger.error(err)
				if printFile:
					payload = {
						"type" : "error",
						"reason" : err.response.text
					}
					if self.bm.watcherRegistered:
						self.bm.triggerEvent('onDownload', payload)
				self.plugin.send_event("download", {'id' : id, 'name': fileName, 'failed' : err.response.text })
				self.clearFile(destination)
				return None
			except requests.exceptions.RequestException as e:
				self._logger.error(e)
				if printFile:
					payload = {
						"type" : "error",
					}
					if self.bm.watcherRegistered:
						self.bm.triggerEvent('onDownload', payload)
				self.plugin.send_event("download", {'id' : id, 'name': fileName, 'failed' : "Server Error"})
				self.clearFile(destination)
				return None

			self.activeDownload = False
			self._canceled = False
			self._activeRequest = None
			downloadQueue.task_done()

	def cancel(self):
		if self.activeDownload:
			if self._activeRequest:
				self._activeRequest.close()

			self._manager._logger.warn('Download canceled requested for %s' % self.activeDownload)
			self._canceled = True

	def downloadCanceled(self, id, fileName):
		if fileName:
			payload = {
						"type" : "cancelled",
						"id"  : id
				}
			self.bm.triggerEvent('onDownload', payload)
		self.plugin.send_event("download", {'id' : id, 'name': fileName, 'canceled' : True})
		self._canceled = False

	def clearFile(self, destination):
		if destination and os.path.exists(destination):
			os.remove(destination)

class DownloadManager(object):
	_maxWorkers = 3

	def __init__(self, astroprintCloud):
		self.astroprintCloud = astroprintCloud
		self.plugin = astroprintCloud.plugin
		self.queue = Queue()
		self._workers = []
		self._logger = self.plugin.get_logger()
		for i in range(self._maxWorkers):
			w = DownloadWorker(self)
			w.daemon = True
			self._workers.append( w )
			w.start()

	def isDownloading(self, id):
		for w in self._workers:
			if w.activeDownload == id:
				return True

		return False

	def startDownload(self, item):
		self.queue.put(item)

	def cancelDownload(self, id):
		for w in self._workers:
			if w.activeDownload == id:
				w.cancel()
				return True

		return False

	def shutdown(self):
		self._logger.info('Shutting down Download Manager...')
		for w in self._workers:
			self.queue.put('shutdown')
			if w.activeDownload:
				w.cancel()
