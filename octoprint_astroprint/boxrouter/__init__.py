# coding=utf-8
from __future__ import absolute_import,  unicode_literals

__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2017-2020 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

# singleton
_instance = None

def boxrouterManager(plugin):
	global _instance
	if _instance is None:
		_instance = AstroprintBoxRouter(plugin)
	return _instance

import json
import threading
import socket
import os
import sys
import weakref
import uuid

from time import sleep, time

from ws4py.client.threadedclient import WebSocketClient
from ws4py.messaging import PingControlMessage

import octoprint.util

from .handlers import BoxRouterMessageHandler
from .events import EventSender

LINE_CHECK_STRING = 'box'

class AstroprintBoxRouterClient(WebSocketClient):
	def __init__(self, hostname, router, plugin):
		self.connected = False
		self._printerListener = plugin.get_printer_listener()
		self._printer = plugin.get_printer()
		self._lastReceived = 0
		self._lineCheck = None
		self._error = False
		self._weakRefRouter = weakref.ref(router)
		self.plugin = plugin
		self._logger = self.plugin.get_logger()
		self._condition = threading.Condition()
		self._messageHandler = BoxRouterMessageHandler(self._weakRefRouter, self)
		super(AstroprintBoxRouterClient, self).__init__(hostname)

	def get_printer_listener(self):
		return self._printerListener

	def __del__(self):
		router = self._weakRefRouter()
		router.unregisterEvents()

	def send(self, data):
		with self._condition:
			if not self.terminated:
				try:
					super(AstroprintBoxRouterClient, self).send(data)

				except socket.error as e:
					self._logger.error('Error raised during send: %s' % e)

					self._error = True

					#Something happened to the link. Let's try to reset it
					self.close()

	def ponged(self, pong):
		if str(pong) == LINE_CHECK_STRING:
			self.outstandingPings -= 1

	def lineCheck(self, timeout=30):
		while not self.terminated:
			sleep(timeout)
			if self.terminated:
				break

			if self.outstandingPings > 0:
				self._logger.error('The line seems to be down')

				router = self._weakRefRouter()
				router.close()
				router._doRetry()
				break

			if time() - self._lastReceived > timeout:
				try:
					self.send(PingControlMessage(data=LINE_CHECK_STRING))
					self.outstandingPings += 1

				except socket.error:
					self._logger.error("Line Check failed to send")

					#retry connection
					router = self._weakRefRouter()
					router.close()
					router._doRetry()

		self._lineCheckThread = None

	def terminate(self):
		#This is code to fix an apparent error in ws4py
		try:
			self._th = None #If this is not freed, the socket can't be freed because of circular references
			super(AstroprintBoxRouterClient, self).terminate()

		except AttributeError as e:
			if self.stream is None:
				self.environ = None
			else:
				raise e

	def opened(self):
		self.outstandingPings = 0
		self._lineCheckThread = threading.Thread(target=self.lineCheck)
		self._lineCheckThread.daemon = True
		self._error = False
		self._lineCheckThread.start()

	def closed(self, code, reason=None):
		#only retry if the connection was terminated by the remote or a link check failure (silentReconnect)
		router = self._weakRefRouter()

		if self._error or (self.server_terminated and router and router.connected):
			router.close()
			router._doRetry()

	def received_message(self, m):
		self._lastReceived = time()
		msg = json.loads(str(m))
		method  = getattr(self._messageHandler, msg['type'], None)
		if method:
			response = method(msg)
			if response is not None:
				self.send(json.dumps(response))

		else:
			self._logger.warn('Unknown message type [%s] received' % msg['type'])


class AstroprintBoxRouter(object):
	RETRY_SCHEDULE = [2, 2, 4, 10, 20, 30, 60, 120, 240, 480, 3600, 10800, 28800, 43200, 86400, 86400] #seconds to wait before retrying. When all exahusted it gives up

	STATUS_DISCONNECTED = 'disconnected'
	STATUS_CONNECTING = 'connecting'
	STATUS_CONNECTED = 'connected'
	STATUS_ERROR = 'error'

	def __init__(self, plugin):
		self._pendingClientRequests = {}
		self._retries = 0
		self._retryTimer = None
		self.ws = None
		self._silentReconnect = False
		self.status = self.STATUS_DISCONNECTED
		self.connected = False
		self.authenticated = False
		self.plugin = plugin
		self.watcherRegistered = False
		self._printerListener = None
		self._eventSender = None
		self._settings = self.plugin.get_settings()
		self._logger = self.plugin.get_logger()
		self._address = self._settings.get(["webSocket"])


	def shutdown(self):
		self._logger.info('Shutting down Box router...')

		if self._retryTimer:
			self._retryTimer.cancel()
			self._retryTimer = None

		self._pendingClientRequests = None
		self.boxrouter_disconnect()

		#make sure we destroy the singleton
		global _instance
		_instance = None

	def boxrouter_connect(self):
		if not self.connected:
			if self.plugin.user:
				self._logger.info("Connecting to Box Router as [%s - %s]" % (self._settings.get(["boxName"]), self.plugin.boxId))
				self._publicKey = self.plugin.user['id']
				self._privateKey = self.plugin.user['accessKey']
				accessKey = self.plugin.astroprintCloud.getToken()
				##if self._publicKey and self._privateKey:
				if accessKey:
					self.status = self.STATUS_CONNECTING
					self.plugin.send_event("boxrouterStatus", self.STATUS_CONNECTING)

					try:
						if self._retryTimer:
							#This is in case the user tried to connect and there was a pending retry
							self._retryTimer.cancel()
							self._retryTimer = None
							#If it fails, the retry sequence should restart
							self._retries = 0

						if self.ws and not self.ws.terminated:
							self.ws.terminate()

						self.ws = AstroprintBoxRouterClient(self._address, self, self.plugin)
						self.ws.connect()
						self.connected = True
						if not self._printerListener:
							self._printerListener = self.plugin.get_printer_listener()
						self._printerListener.addWatcher(self)

					except Exception as e:
						self._logger.error("Error connecting to boxrouter: %s" % e)
						self.connected = False
						self.status = self.STATUS_ERROR
						self.plugin.send_event("boxrouterStatus", self.STATUS_ERROR)

						if self.ws:
							self.ws.terminate()
							self.ws = None

						self._doRetry(False) #This one should not be silent

					return True

		return False

	def boxrouter_disconnect(self):
		self.close()

	def close(self):
		if self.connected:
			self.authenticated = False
			self.connected = False

			self._publicKey = None
			self._privateKey = None
			self.status = self.STATUS_DISCONNECTED
			self.plugin.send_event("boxrouterStatus", self.STATUS_DISCONNECTED)

			self._printerListener.removeWatcher()

			if self.ws:
				self.unregisterEvents()
				if not self.ws.terminated:
					self.ws.terminate()

				self.ws = None

	def _doRetry(self, silent=True):
		if self._retries < len(self.RETRY_SCHEDULE):
			def retry():
				self._retries += 1
				self._logger.info('Retrying boxrouter connection. Retry #%d' % self._retries)
				self._silentReconnect = silent
				self._retryTimer = None
				self.boxrouter_connect()

			if not self._retryTimer:
				self._logger.info('Waiting %d secs before retrying...' % self.RETRY_SCHEDULE[self._retries])
				self._retryTimer = threading.Timer(self.RETRY_SCHEDULE[self._retries] , retry )
				self._retryTimer.start()

		else:
			self._logger.info('No more retries. Giving up...')
			self.status = self.STATUS_DISCONNECTED
			self.plugin.send_event("boxrouterStatus", self.STATUS_DISCONNECTED)
			self._retries = 0
			self._retryTimer = None


	def cancelRetry(self):
		if self._retryTimer:
			self._retryTimer.cancel()
			self._retryTimer = None

	def completeClientRequest(self, reqId, data):
		if reqId in self._pendingClientRequests:
			req = self._pendingClientRequests[reqId]
			del self._pendingClientRequests[reqId]

			if req["callback"]:
				args = req["args"] or []
				req["callback"](*([data] + args))

		else:
			self._logger.warn('Attempting to deliver a client response for a request[%s] that\'s no longer pending' % reqId)

	def sendRequestToClient(self, clientId, type, data, timeout, respCallback, args=None):
		reqId = uuid.uuid4().hex

		if self.send({
			'type': 'request_to_client',
			'data': {
				'clientId': clientId,
				'timeout': timeout,
				'reqId': reqId,
				'type': type,
				'payload': data
			}
		}):
			self._pendingClientRequests[reqId] = {
				'callback': respCallback,
				'args': args,
				'timeout': timeout
			}

	def sendEventToClient(self, clientId, type, data):
		self.send({
			'type': 'send_event_to_client',
			'data': {
				'clientId': clientId,
				'eventType': type,
				'eventData': data
			}
		})

	def send(self, data):
		if self.ws and self.connected:
			self.ws.send(json.dumps(data))
			return True

		else:
			self._logger.error('Unable to send data: Socket not active')
			return False

	def sendEvent(self, event, data):
		if self.watcherRegistered:
			dataToSend = ({
					'type': 'send_event',
					'data': {
						'eventType': event,
						'eventData': data
					}
				})
			return self.send(dataToSend)
		else:
			return True

	def registerEvents(self):
		if not self._printerListener:
			self._printerListener = self.plugin.get_printer_listener()
		if not self._eventSender:
			self._eventSender = EventSender(self)
			self._eventSender.connect()
		self.watcherRegistered = True

	def unregisterEvents(self):
		self.watcherRegistered = False

	def broadcastEvent(self, event, data):
		if self._eventSender:
			self._eventSender.sendUpdate(event, data)

	def triggerEvent(self, event, data):
		if self._eventSender:
			method  = getattr(self._eventSender, event, None)
			if method:
				 method(data)
			else:
				self._logger.warn('Unknown event type [%s] received' % event)


	def processAuthenticate(self, data):
		if data:
			self._silentReconnect = False
			if 'error' in data and data['error']:
				self._logger.warn("Box Router Authentication Error: %s" % data['message'] if 'message' in data else 'Unkonwn authentication error')
				self.status = self.STATUS_ERROR
				self.plugin.send_event("boxrouterStatus", self.STATUS_ERROR)
				self.close()
				errorType = data['type'] if 'type' in data else None

				if errorType == 'box_id_in_use':
					self._logger.warn("Box Router is reporting that the box id [%s] is in use by another box. Is this image a clone of another? consider deleting the file at %s" % (self.plugin.boxId, os.path.join(os.path.dirname(self._settings._configfile), "box-id")))
				elif 'should_retry' in data and data['should_retry']:
					self._doRetry()
				elif errorType == 'unable_to_authenticate':
					self._logger.info("Box Router unable to authenticate user. No retries, logging out")
					self.plugin.astroprintCloud.unauthorizedHandler()

			elif 'success' in data and data['success']:
				self._logger.info("Box Router connected to astroprint service")
				if 'groupId' in data:
					self.plugin.astroprintCloud.updateFleetInfo(data['orgId'], data['groupId'])
				self.authenticated = True
				self._retries = 0
				self._retryTimer = None
				self.status = self.STATUS_CONNECTED
				self.plugin.send_event("boxrouterStatus", self.STATUS_CONNECTED)
				self.plugin.astroprintCloud.sendCurrentData()

			return None

		else:
			boxName = self._settings.get(["boxName"])
			platform = sys.platform
			localIpAddress = octoprint.util.address_for_client("google.com", 80)
			mayor, minor, build = self.plugin.get_plugin_version().split(".")
			return {
			 	'type': 'auth',
			 	'data': {
			 		'silentReconnect': self._silentReconnect,
			 		'boxId': self.plugin.boxId,
			 		'variantId': self._settings.get(["product_variant_id"]),
			 		'boxName': boxName,
			 		'swVersion': "OctoPrint Plugin - v%s.%s(%s)" % (mayor, minor, build),
			 		'platform': platform,
			 		'localIpAddress': localIpAddress,
					'accessToken' : self.plugin.astroprintCloud.getToken(),
			 		#'publicKey': self._publicKey,
			 		#'privateKey': self._privateKey,
					'printerModel': self._settings.get(["printerModel"]) if self._settings.get(['printerModel'])['id'] else None
			 	}
			}
