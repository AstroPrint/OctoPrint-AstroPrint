# coding=utf-8
from __future__ import absolute_import,   unicode_literals

__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2017-2020 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import time
import requests
import traceback
import warnings

## Python2/3 compatibile import
try:
	from StringIO import StringIO
except ImportError:
	from io import StringIO

from threading import Event


try:
	from PIL import Image
except ImportError:
	Image = None
	import subprocess
	traceback.print_exc()
	warnings.warn("PIL/Pillow is not available. Will fallback to "
				  + "ImageMagick, make sure it is installed.")

# singleton
_instance = None

def cameraManager(plugin):
	global _instance
	if _instance is None:
		_instance = CameraManager(plugin)
	return _instance

import threading
from threading import Thread
import os.path
import time
import logging

from sys import platform

#
# Camera Manager base class
#

class CameraManager(object):
	def __init__(self, plugin):
		self.name = None
		self.cameraActive = False
		self.astroprintCloud = None #set up when astroprint cloud is initialized

		#RECTIFYNIG default settings
		self.plugin = plugin
		self._settings = self.plugin.get_settings()
		self._logger = self.plugin.get_logger()
		self._printer = self.plugin.get_printer()
		self.checkCameraStatus()
		self._image_transpose = (self._settings.global_get(["webcam", "flipH"]) or
				self._settings.global_get(["webcam", "flipV"]) or
				self._settings.global_get(["webcam", "rotate90"]))
		self._photos = {} # To hold sync photos
		self.timelapseWorker = None
		self.timelapseInfo = None
		self.plugin.get_printer_listener().cameraManager = self

	def layerChanged(self):
		if self.timelapseInfo and self.timelapseInfo['freq'] == "layer":
			self.addPhotoToTimelapse(self.timelapseInfo['id'])

	def checkCameraStatus(self):
		snapshotUrl = self._settings.global_get(["webcam", "snapshot"])
		camUrl = self._settings.global_get(["webcam", "stream"])
		if snapshotUrl and camUrl:
			try:
				r = requests.get(
					snapshotUrl
				)
				if r.status_code == 200:
					camera = True
				else :
					camera = False

			except Exception as e:
				self._logger.error("Error getting camera status: %s" % e)
				camera = False

		else:
			camera = False
		if camera != self.cameraActive:
			self.cameraActive = camera
			self.plugin.send_event("cameraStatus", self.cameraActive)
			self.plugin.sendSocketInfo()
		self._settings.set(['camera'], self.cameraActive)

	def cameraError(self):
		if self.cameraActive:
			self.cameraActive = False
			self._settings.set(['camera'], self.cameraActive)
			self.plugin.send_event("cameraStatus", self.cameraActive)
			if self.astroprintCloud:
				self.astroprintCloud.sendCurrentData()

	def printStarted(self):
		self.timelapseInfo = None

	def cameraConnected(self):
		if not self.cameraActive:
			self.cameraActive = True
			self._settings.set(['camera'], self.cameraActive)
			self.plugin.send_event("cameraStatus", self.cameraActive)
			if self.astroprintCloud:
				self.astroprintCloud.sendCurrentData()

	def shutdown(self):
		self._logger.info('Shutting down Camera Manager...')
		if self.timelapseWorker:
			self.timelapseWorker.stop()
			self.timelapseWorker = None

		global _instance
		_instance = None

	def getPic(self):
		if not self.cameraActive:
			return None
		else:
			snapshotUrl = self._settings.global_get(["webcam", "snapshot"])

			try:
				r = requests.get(snapshotUrl)
				pic = r.content
				if pic is not None:
					if self._settings.global_get(["webcam", "flipH"]) or self._settings.global_get(["webcam", "flipV"]) or self._settings.global_get(["webcam", "rotate90"]):
						if Image:
							buf = StringIO()
							buf.write(pic)
							image = Image.open(buf)
							if self._settings.global_get(["webcam", "flipH"]):
								image = image.transpose(Image.FLIP_LEFT_RIGHT)
							if self._settings.global_get(["webcam", "flipV"]):
								image = image.transpose(Image.FLIP_TOP_BOTTOM)
							if self._settings.global_get(["webcam", "rotate90"]):
								image = image.transpose(Image.ROTATE_90)
							transformedImage = StringIO()
							image.save(transformedImage, format="jpeg")
							transformedImage.seek(0, 2)
							transformedImage.seek(0)
							pic = transformedImage.read()
						else:
							args = ["convert", "-"]
							if self._settings.global_get(["webcam", "flipV"]):
								args += ["-flip"]
							if self._settings.global_get(["webcam", "flipH"]):
								args += ["-flop"]
							if self._settings.global_get(["webcam", "rotate90"]):
								args += ["-rotate", "90"]
							args += "jpeg:-"
							p = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
							pic, _ = p.communicate(pic)

				if not self.cameraActive:
					self.cameraConnected()
				return pic
			except Exception as e:
				self._logger.exception("Error getting pic: %s" % e)
				self.cameraError()
				return None



	def addPhotoToTimelapse(self, timelapseId, waitForPhoto = False):
		#Build text
		'''
		printerData = self.plugin.get_printer_listener().get_progress()
		text = "%d%% - Layer %s%s" % (
			printerData['progress']['completion'],
			str(printerData['progress']['currentLayer']) if printerData['progress']['currentLayer'] else '--',
			"/%s" % str(printerData['job']['layerCount'] if printerData['job']['layerCount'] else '')
		)
		'''
		picBuf = self.getPic()

		if picBuf:
			picData = self.astroprintCloud.uploadImageFile(timelapseId, picBuf)
			#we need to check again as it's possible that this was the last
			#pic and the timelapse is closed.
			if picData and self.timelapseInfo:
				self.timelapseInfo['last_photo'] = picData['url']
				#Here we send the box confirmation:
				self.astroprintCloud.bm.triggerEvent('onCaptureInfoChanged', self.timelapseInfo)
				if waitForPhoto:
					return True

		#self.get_pic_async(onDone, text)


	def start_timelapse(self, freq):
		if not self.cameraActive:
			return 'no_camera'

		if freq == '0':
			return 'invalid_frequency'

		if self.timelapseWorker:
			self.stop_timelapse()
		#check that there's a print ongoing otherwise don't start
		current_job = self._printer.get_current_job()
		if not current_job:
			return 'no_print_file_selected'
		printCapture = self.astroprintCloud.startPrintCapture(current_job['file']['name'], current_job['file']['path'])
		if printCapture['error']:
			return printCapture['error']

		else:
			self.timelapseInfo = {
				'id': printCapture['print_id'],
				'freq': freq,
				'paused': False,
				'last_photo': None
			}

			if freq == 'layer':
				# send first pic and subscribe to layer change events
				self.addPhotoToTimelapse(printCapture['print_id'])

			else:

				try:
					freq = float(freq)
				except ValueError:
					self._logger.info("invalid_frequency")
					return 'invalid_frequency'

				self.timelapseInfo['freq'] = freq
				self.timelapseWorker = TimelapseWorker(self, printCapture['print_id'], freq)
				self.timelapseWorker.start()

			return 'success'

		return 'unkonwn_error'

	def update_timelapse(self, freq):
		if self.timelapseInfo and self.timelapseInfo['freq'] != freq:
			if freq == 'layer':
				if self.timelapseWorker and not self.timelapseWorker.isPaused():
					self.pause_timelapse()

				# subscribe to layer change events
			else:
				try:
					freq = float(freq)
				except ValueError as e:
					self._logger.error("Error updating timelapse: %s" % e)
					return False

				# if subscribed to layer change events, unsubscribe here

				if freq == 0:
					self.pause_timelapse()
				elif not self.timelapseWorker:
					self.timelapseWorker = TimelapseWorker(self, self.timelapseInfo['id'], freq)
					self.timelapseWorker.start()
				elif self.timelapseWorker.isPaused():
					self.timelapseWorker.timelapseFreq = freq
					self.resume_timelapse()
				else:
					self.timelapseWorker.timelapseFreq = freq

			self.timelapseInfo['freq'] = freq

			return True

		return False

	def stop_timelapse(self, takeLastPhoto = False):

		if self.timelapseWorker:
			self.timelapseWorker.stop()
			self.timelapseWorker = None

		if takeLastPhoto and self.timelapseInfo:
			self.addPhotoToTimelapse(self.timelapseInfo['id'])

		self.timelapseInfo = None
		self.astroprintCloud.bm.triggerEvent('onCaptureInfoChanged', self.timelapseInfo)

		return True

	def pause_timelapse(self):
		if self.timelapseWorker:
			if not self.timelapseWorker.isPaused():
				self.timelapseWorker.pause()
				self.timelapseInfo['paused'] = True
				self.astroprintCloud.bm.triggerEvent('onCaptureInfoChanged', self.timelapseInfo)
			return True

		return False

	def resume_timelapse(self):
		if self.timelapseWorker:
			if self.timelapseWorker.isPaused():
				self.timelapseWorker.resume()
				self.timelapseInfo['paused'] = False
				self.astroprintCloud.bm.triggerEvent('onCaptureInfoChanged', self.timelapseInfo)
			return True

		return False

	def is_timelapse_active(self):
		return self.timelapseWorker is not None

	@property
	def capabilities(self):
		return []

#
# Thread to take timed timelapse pictures
#

class TimelapseWorker(threading.Thread):
	def __init__(self, manager, timelapseId, timelapseFreq):
		super(TimelapseWorker, self).__init__()

		self._stopExecution = False
		self._cm = manager
		self._resumeFromPause = threading.Event()

		self.daemon = True
		self.timelapseId = timelapseId
		self.timelapseFreq = timelapseFreq
		self._logger = manager._logger

	def run(self):
		lastUpload = 0
		self._resumeFromPause.set()
		while not self._stopExecution:
			if (time.time() - lastUpload) >= self.timelapseFreq and self._cm.addPhotoToTimelapse(self.timelapseId, True):
				lastUpload = time.time()

			time.sleep(1)
			self._resumeFromPause.wait()

	def stop(self):
		self._stopExecution = True
		if self.isPaused():
			self.resume()

		self.join()

	def pause(self):
		self._resumeFromPause.clear()

	def resume(self):
		self._resumeFromPause.set()

	def isPaused(self):
		return not self._resumeFromPause.isSet()
