# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2017-2019 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import json

from copy import deepcopy

class EventSender(object):
	def __init__(self, socket):
		self._socket = socket
		self._logger = socket.plugin.get_logger()

	def connect(self):
		self._lastSent = {
			'temp_update': None,
			'status_update': None,
			'printing_progress': None,
			'print_capture': None,
			'print_file_download': None,
			'filament_update' : None,
		}


	def onCaptureInfoChanged(self, payload):
		self.sendUpdate('print_capture', payload)

	def filamentChanged(self, payload):
		self.sendUpdate('filament_update', payload)

	def onDownload(self, payload):
		data = {
			'id': payload['id'],
			'selected': False
		}

		if payload['type'] == 'error':
			data['error'] = True
			data['message'] = payload['reason'] if 'reason' in payload else 'Problem downloading'

		elif payload['type'] == 'cancelled':
			data['cancelled'] = True

		else:
			data['progress'] = 100 if payload['type'] == 'success' else payload['progress']

		self.sendUpdate('print_file_download', data)

	def onDownloadComplete(self, data):
		if data['isBeingPrinted']:
			payload = {
				'id': data['id'],
				'progress': 100,
				'selected': True
			}
		else :
			payload = {
				'id': data['id'],
				'progress': 100,
				'error': True,
				'message': 'Unable to start printing',
				'selected': False
			}
		self.sendUpdate('print_file_download', payload)



	def sendLastUpdate(self, event):
		if event in self._lastSent:
			self._send(event, self._lastSent[event])

	def sendUpdate(self, event, data):
		if self._lastSent[event] != data and self._send(event, data):
			self._lastSent[event] = deepcopy(data) if data else None

	def _send(self, event, data):
			try:
				self._socket.sendEvent(event, data)
				return True

			except Exception as e:
				self._logger.error( 'Error sending [%s] event: %s' % (event, e) )
				return False
