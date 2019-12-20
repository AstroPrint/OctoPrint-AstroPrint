# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2017-2019 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import base64
import threading
import re

from time import sleep

class RequestHandler(object):
	def __init__(self, wsClient):

		self.wsClient = wsClient
		self.plugin = self.wsClient.plugin
		self.astroprintCloud = self.plugin.astroprintCloud
		self._printer = self.plugin.get_printer()
		self._printerListener = self.wsClient.get_printer_listener()
		self._logger = self.plugin.get_logger()
		self.cameraManager = self.plugin.cameraManager
		self._settings = self.plugin.get_settings()

	def initial_state(self, data, clientId, done):
		if not self.astroprintCloud:
			self.astroprintCloud = self.plugin.astroprintCloud
		dataProfile = self.wsClient.plugin._printer_profile_manager.get_current_or_default()

		profile = {
			'driver': "marlin", #At the moment octopi only supports marlin
			'extruder_count': dataProfile['extruder']['count'],
			'max_nozzle_temp': self._settings.get(["max_nozzle_temp"]),
			'max_bed_temp': self._settings.get(["max_bed_temp"]),
			'heated_bed': dataProfile['heatedBed'],
			'cancel_gcode': ['G28 X0 Y0'],
			'invert_z': dataProfile['axes']['z']['inverted'],
			'printer_model': self._settings.get(["printerModel"]) if self._settings.get(['printerModel'])['id']  else None,
			'filament' : self._settings.get(["filament"])
		}

		state = {
			'printing': self._printer.is_printing(),
			'heatingUp': self.plugin.printerIsHeating(),
			'operational': self._printer.is_operational(),
			'paused': self._printer.is_paused(),
			'camera': True, #self.cameraManager.cameraActive,
			'filament' : self._settings.get(["filament"]),
			'printCapture': self.cameraManager.timelapseInfo,
			'profile': profile,
			'capabilities': ['remotePrint', 'multiExtruders', 'allowPrintFile', 'acceptPrintJobId'],
			'tool' : self.plugin.currentTool()
		}

		if state['printing'] or state['paused']:
			#Let's add info about the ongoing print job
			current_job = self._printer.get_current_job()
			printFile = self.astroprintCloud.db.getPrintFileByOctoPrintPath(current_job['file']['path'])

			state['job'] = {
				"estimatedPrintTime": current_job['estimatedPrintTime'],
				"layerCount": self._printerListener.get_analyzed_job_layers()['layerCount'] if self._printerListener.get_analyzed_job_layers() else None ,
				"file": {
					"origin": current_job['file']['origin'],
					"rendered_image": printFile.renderedImage if printFile else None,
					"name" : printFile.name if printFile else current_job['file']['name'],
					"cloudId" : printFile.printFileId if printFile else None,
					"date": current_job['file']['date'],
					"printFileName": printFile.printFileName if printFile else None,
					"size": current_job['file']['size'],
					},
				"filament": current_job['filament'],
			}
			state['progress'] =  self._printerListener.get_progress()


		done(state)

	def job_info(self, data, clientId, done):
		if self._printerListener.get_job_data() and not self._printerListener.get_job_data()['layerCount']:
			t = threading.Timer(0.5, self.job_info, [data, clientId, done])
			t.start()
		else:
			done(self._printerListener.get_job_data())

	def printerCommand(self, data, clientId, done):
		self._handleCommandGroup(PrinterCommandHandler, data, clientId, done, self.plugin)

	def printCapture(self, data, clientId, done):
		freq = data['freq']
		if freq:
			cm = self.cameraManager

			if cm.timelapseInfo:
				if not cm.update_timelapse(freq):
					done({
						'error': True,
						'message': 'Error updating the print capture'
					})
					return

			else:
				r = cm.start_timelapse(freq)
				if r != 'success':
					done({
						'error': True,
						'message': 'Error creating the print capture: %s' % r
					})
					return
		else:
			done({
				'error': True,
				'message': 'Frequency required'
			})
			return

		done(None)

	def signoff(self, data, clientId, done):
		threading.Timer(1, self.astroprintCloud.unauthorizedHandler, [False]).start()
		done(None)

	def print_file(self, data, clientId, done):
		print_file_id = data['printFileId']

		#DANIEL AQUI OBTENEGO ID DE PRINTJOB Y DE PRINTFILE Y LO MANDO A CLOUD CLASS
		if 'printJobId' in data :
			print_job_data = {'print_job_id' : data['printJobId'], 'print_file' : print_file_id}
		else :
			print_job_data = None

		state = {
				"type": "progress",
				"id": print_file_id,
				"progress": 0
			}
		done(state)
		# DANIEL AQUI LO MANDO
		self.astroprintCloud.printFile(print_file_id, print_job_data, True)

	def cancel_download(self, data, clientId, done):
		print_file_id = data['printFileId']
		self.astroprintCloud.cancelDownload(print_file_id)

		done(None)

	def set_filament(self, data, clientId, done):

		filament = {}

		if data['filament'] and data['filament']['name'] and data['filament']['color']:
			filament['name'] = data['filament']['name']
			#Better to make sure that are getting right color codes
			if re.search(r'^#(?:[0-9a-fA-F]{3}){1,2}$', data['filament']['color']):
				filament['color'] = data['filament']['color']
				self._settings.set(['filament'], filament)
				self._settings.save()
				self.astroprintCloud.bm.triggerEvent('filamentChanged', data)
				done(None)
			else:
				done({
					'error': True,
					'message': 'Invalid color code'
				})

		else:
			data['filament'] = None
			self._settings.set(['filament'], None)
			self._settings.save()
			self.astroprintCloud.bm.triggerEvent('filamentChanged', data)
			done(None)

	#set CommandGroup for future camera and 2p2 updates
	def _handleCommandGroup(self, handlerClass, data, clientId, done, plugin = None):
		handler = handlerClass(plugin)

		command = data['command']
		options = data['options']

		method  = getattr(handler, command, None)
		if method:
			method(options, clientId, done)

		else:
			done({
				'error': True,
				'message': '%s::%s is not supported' % (handlerClass, command)
			})


# Printer Command Group Handler
class PrinterCommandHandler(object):

	def __init__(self, plugin):
		self.plugin = plugin
		self._printer = self.plugin.get_printer()
		self._settings = self.plugin.get_settings()
		self._logger = self.plugin.get_logger()
		self.cameraManager = self.plugin.cameraManager

	def pause(self, data, clientId, done):
		self._printer.pause_print()
		done(None)

	def resume(self, data, clientId, done):
		self._printer.resume_print()
		done(None)

	def cancel(self, data, clientId, done):
		data = {'print_job_id': self.plugin.astroprintCloud.currentPrintingJob}
		self._printer.cancel_print()
		done(None)

	def photo(self, data, clientId, done):
		pic = self.cameraManager.getPic()

		if pic is not None:
			done({
				'success': True,
				'image_data': base64.b64encode(pic)
			})
		else:
			done({
				'success': False,
				'image_data': ''
			})
