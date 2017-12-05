# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2017 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import weakref
import json

from .requesthandler import RequestHandler

class BoxRouterMessageHandler(object):
	def __init__(self, weakRefBoxRouter, wsClient):
		self._weakRefBoxRouter = weakRefBoxRouter
		self._weakWs = weakref.ref(wsClient)
		self._logger = wsClient.plugin.get_logger()
		self._printer = wsClient.plugin.get_printer()
		self._handler = None
		self._subscribers = 0

	def auth(self, msg):
		router = self._weakRefBoxRouter()
		if router:
			return router.processAuthenticate((msg['data'] if 'data' in msg else None))
		else:
			return None

	def set_temp(self, msg):
		payload = {}

		if self._printer.is_operational():
			payload = msg['payload']
			self._printer.set_temperature(payload['target'] or 0.0, payload['value'] or 0.0)
		return None

	def update_subscribers(self, msg):
		wsClient = self._weakWs()

		if wsClient:
			self._subscribers += int(msg['data'])
			router = self._weakRefBoxRouter()
			if self._subscribers > 0:
				router.registerEvents()
			else:
				self._subscribers = 0
				router.unregisterEvents()

		return None

	def force_event(self, msg):
		router = self._weakRefBoxRouter()

		if router:
			router.triggerEvent('sendLastUpdate', msg['data'])

		return None

	def request(self, msg):

		wsClient = self._weakWs()

		if wsClient:
			if not self._handler:
				self._handler = RequestHandler(wsClient)
			response = None

			try:
				request = msg['data']['type']
				reqId = msg['reqId']
				clientId = msg['clientId']
				data = msg['data']['payload']

				method  = getattr(self._handler, request, None)
				if method:
					def sendResponse(result):
						if result is None:
							result = {'success': True}

						wsClient.send(json.dumps({
							'type': 'req_response',
							'reqId': reqId,
							'data': result
						}))

					method(data, clientId, sendResponse)

				else:
					response = {
						'error': True,
						'message': 'This Box does not recognize the request type [%s]' % request
					}

			except Exception as e:
				message = 'Error sending [%s] response: %s' % (request, e)
				self._logger.error( message , exc_info= True)
				response = {'error': True, 'message': message }

			if response:
				wsClient.send(json.dumps({
					'type': 'req_response',
					'reqId': reqId,
					'data': response
				}))

			#else:
				# this means that the handler is asynchronous
				# and will respond when done
				# we should probably have a timeout here too
				# even though there's already one at the boxrouter

	def response_from_client(self, msg):

		router = self._weakRefBoxRouter()

		if router:
			router.completeClientRequest(msg['reqId'], msg['data'])
