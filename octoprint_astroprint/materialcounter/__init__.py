# coding=utf-8
from __future__ import absolute_import, division, print_function, unicode_literals

__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2017-2020 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import re

from copy import copy

class MaterialCounter(object):

	#Extrusion modes
	EXTRUSION_MODE_ABSOLUTE = 1
	EXTRUSION_MODE_RELATIVE = 2

	def __init__(self, plugin):
		self.plugin = plugin
		self._logger = self.plugin.get_logger()
		self._extrusionMode = self.EXTRUSION_MODE_ABSOLUTE
		self._activeTool = "0"
		self._lastExtruderLengthReset = {"0": 0}
		self._consumedFilament = {"0": 0}
		self._lastExtrusion = {"0": 0}


		# regexes
		floatPattern = r"[-+]?[0-9]*\.?[0-9]+"
		intPattern = r"\d+"
		self._regex_paramEFloat = re.compile("E(%s)" % floatPattern)
		self._regex_paramTInt = re.compile("T(%s)" % intPattern)


	@property
	def extrusionMode(self):
		return self._extrusionMode

	@property
	def consumedFilament(self):
		if self._consumedFilament and self._extrusionMode == self.EXTRUSION_MODE_ABSOLUTE:
			tool = self._activeTool
			consumedFilament = copy(self._consumedFilament)

			try:
				consumedFilament[tool] += ( self._lastExtrusion[tool] - self._lastExtruderLengthReset[tool] )

			except KeyError:
				return None

			return consumedFilament

		else:
			return self._consumedFilament

	@property
	def totalConsumedFilament(self):
		consumedFilament = self.consumedFilament
		return sum([consumedFilament[k] for k in consumedFilament.keys()])

	def startPrint(self):
		tool = self._activeTool
		self._lastExtruderLengthReset = {tool: 0}
		self._consumedFilament = {tool: 0}
		self._lastExtrusion = {tool: 0}


	def _gcode_T(self, cmd): #changeActiveTool
		toolMatch = self._regex_paramTInt.search(cmd)
		if toolMatch:
			tool = int(toolMatch.group(1))
			if self._activeTool != tool:
				newTool = str(tool)
				oldTool =  str(self._activeTool)
				#Make sure the head is registered
				if newTool not in self._consumedFilament:
					self._consumedFilament[newTool] = 0
					self._lastExtruderLengthReset[newTool] = 0
					self._lastExtrusion[newTool] = 0

				if self._extrusionMode == self.EXTRUSION_MODE_ABSOLUTE:
					if oldTool in self.consumedFilament and oldTool in self._lastExtrusion and oldTool in self._lastExtruderLengthReset:
						self.consumedFilament[oldTool] += ( self._lastExtrusion[oldTool] - self._lastExtruderLengthReset[oldTool] )
						self._lastExtruderLengthReset[oldTool] = self.consumedFilament[oldTool]
					else:
						self._logger.error('Unkonwn previous tool %s when trying to change to new tool %s' % (oldTool, newTool))
				self._activeTool = newTool

	def _gcode_G92(self, cmd):
		# At the moment this command is only relevant in Absolute Extrusion Mode
		if self._extrusionMode == self.EXTRUSION_MODE_ABSOLUTE:
			eValue = None

			if cmd.strip() == 'G92': #A simple G92 command resets all axis so E is now set to 0
				eValue = 0
			elif 'E' in cmd:
				match = self._regex_paramEFloat.search(cmd)
				if match:
					try:
						eValue = float(match.group(1))

					except ValueError:
						pass

			if eValue is not None:
				#There has been an E reset
				#resetExtruderLength:
				tool = self._activeTool
				if self._extrusionMode == self.EXTRUSION_MODE_ABSOLUTE:
					# We add what we have to the total for the his tool head
					self._consumedFilament[tool] += ( self._lastExtrusion[tool] - self._lastExtruderLengthReset[tool] )

				self._lastExtruderLengthReset[tool] = eValue
				self._lastExtrusion[tool] = eValue


	def _gcode_G0(self, cmd):
		if 'E' in cmd:
			match = self._regex_paramEFloat.search(cmd)
			if match:
				try:
					#reportExtrusion
					length = float(match.group(1))
					if self._extrusionMode == self.EXTRUSION_MODE_RELATIVE:
						if length > 0: #never report retractions
							self._consumedFilament[self._activeTool] += length

					else: # EXTRUSION_MODE_ABSOLUTE
						tool = self._activeTool

						if length > self._lastExtrusion[tool]: #never report retractions
							self._lastExtrusion[tool] = length

				except ValueError:
					pass


	_gcode_G1 = _gcode_G0

	def _gcode_M82(self, cmd): #Set to absolute extrusion mode
		self._extrusionMode = self.EXTRUSION_MODE_ABSOLUTE


	def _gcode_M83(self, cmd): #Set to relative extrusion mode
		self._extrusionMode = self.EXTRUSION_MODE_RELATIVE
		tool = self._activeTool
		#it was absolute before so we add what we had to the active head counter
		self._consumedFilament[tool] += ( self._lastExtrusion[tool] - self._lastExtruderLengthReset[tool] )


	# In Marlin G91 and G90 also change the relative nature of extrusion
	_gcode_G90 = _gcode_M82 #Set Absolute
	_gcode_G91 = _gcode_M83 #Set Relative





