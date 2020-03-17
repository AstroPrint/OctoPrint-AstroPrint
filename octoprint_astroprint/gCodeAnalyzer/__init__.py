# coding=utf-8
from __future__ import absolute_import,   unicode_literals

__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2017-2020 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import json

from threading import Thread
from sarge import run, Capture

class GCodeAnalyzer(Thread):

	def __init__(self,filename,layersInfo,readyCallback,exceptionCallback,parent, plugin):

		self._logger = plugin.get_logger()

		super(GCodeAnalyzer, self).__init__()

		self.plugin = plugin
		self.filename = filename

		self.readyCallback = readyCallback
		self.exceptionCallback = exceptionCallback
		self.layersInfo = layersInfo
		self.daemon = True

		self.layerList = None
		self.totalPrintTime = None
		self.layerCount = None
		self.size = None
		self.layerHeight = None
		self.totalFilament = None
		self.parent = parent

	def makeCalcs(self):
		self.start()

	def run(self):
		gcodeData = []
		try:
			pipe = run(
				('%s/util/AstroprintGCodeAnalyzer "%s" 1' if self.layersInfo else '%s/util/AstroprintGCodeAnalyzer "%s"') % (
					self.plugin._basefolder,
					self.filename
				), stdout=Capture())

			if pipe.returncode == 0:
				try:
					gcodeData = json.loads(pipe.stdout.text)

					if self.layersInfo:
						self.layerList =  gcodeData['layers']

					self.totalPrintTime = gcodeData['print_time']

					self.layerCount = gcodeData['layer_count']

					self.size = gcodeData['size']

					self.layerHeight = gcodeData['layer_height']

					self.totalFilament = None#total_filament has not got any information

					self.readyCallback(self.layerList,self.totalPrintTime,self.layerCount,self.size,self.layerHeight,self.totalFilament,self.parent)


				except ValueError:
					self._logger.error("Bad gcode data returned: %s" % pipe.stdout.text)
					gcodeData = None

					if self.exceptionCallback:
						parameters = {}
						parameters['parent'] = self.parent
						parameters['filename'] = self.filename

						self.exceptionCallback(parameters)

			else:
				self._logger.warn('Error executing GCode Analyzer')
				gcodeData = None


				if self.exceptionCallback:
					parameters = {}
					parameters['parent'] = self.parent
					parameters['filename'] = self.filename

					self.exceptionCallback(parameters)

		except:
			self._logger.warn('Error running GCode Analyzer')
			gcodeData = None

			if self.exceptionCallback:
				parameters = {}
				parameters['parent'] = self.parent
				parameters['filename'] = self.filename

				self.exceptionCallback(parameters)
