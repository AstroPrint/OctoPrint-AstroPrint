# coding=utf-8
from __future__ import absolute_import

__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2017-2019 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import octoprint.plugin
import json
import sys
import socket
import os
import yaml
import re

from .AstroprintCloud import AstroprintCloud
from .AstroprintDB import AstroprintDB
from .SqliteDB import SqliteDB
from .boxrouter import boxrouterManager
from .cameramanager import cameraManager
from .materialcounter import MaterialCounter
from .printerlistener import PrinterListener

from octoprint.server.util.flask import restricted_access
from octoprint.server import admin_permission
from octoprint.settings import valid_boolean_trues
from octoprint.users import SessionUser
from octoprint.filemanager.destinations import FileDestinations
from octoprint.events import Events

from watchdog.observers import Observer

from flask import request, Blueprint, make_response, jsonify, Response, abort
from flask.ext.login import user_logged_in, user_logged_out


NO_CONTENT = ("", 204)
OK = ("", 200)

class JsonEncoder(json.JSONEncoder):
    def default(self, obj):
        return obj.__dict__

def getJsonCommandFromRequest(request, valid_commands):
	if not "application/json" in request.headers["Content-Type"]:
		return None, None, make_response("Expected content-type JSON", 400)

	data = request.json
	if not "command" in data.keys() or not data["command"] in valid_commands.keys():
		return None, None, make_response("Expected valid command", 400)

	command = data["command"]
	for parameter in valid_commands[command]:
		if not parameter in data:
			return None, None, make_response("Mandatory parameter %s missing for command %s" % (parameter, command), 400)

	return command, data, None

def create_ws_token(public_key= None):
	from itsdangerous import URLSafeTimedSerializer

	s = URLSafeTimedSerializer(octoprint.server.UI_API_KEY)
	return s.dumps({ 'public_key': public_key })


class AstroprintPlugin(octoprint.plugin.SettingsPlugin,
                       octoprint.plugin.AssetPlugin,
					   octoprint.plugin.StartupPlugin,
                       octoprint.plugin.TemplatePlugin,
					   octoprint.plugin.BlueprintPlugin,
					   octoprint.plugin.EventHandlerPlugin,
					   octoprint.printer.PrinterCallback):

	##~~ SettingsPlugin mixin

	def initialize(self):
		self.user = {}
		self.designs = None
		self.db = None
		self.astroprintCloud = None
		self.cameraManager = None
		self.materialCounter= None
		self._printerListener = None

		def logOutHandler(sender, **kwargs):
			self.onLogout()

		def logInHandler(sender, **kwargs):
			for key, value in kwargs.iteritems():
				if isinstance(value, SessionUser):
					self.onLogin()

		self.logOutHandler = logOutHandler
		self.logInHandler = logInHandler

		user_logged_in.connect(logInHandler)
		user_logged_out.connect(logOutHandler)

	def on_after_startup(self):
		self.register_printer_listener()
		self.db = AstroprintDB(self)
		if os.path.isfile(self.get_plugin_data_folder() + "/octoprint_astroprint.db"):
			sqlitledb = SqliteDB(self)
			self.db.saveUser(sqlitledb.getUser())
			self.db.savePrintFiles(sqlitledb.getPrintFiles())
			os.remove(self.get_plugin_data_folder() + "/octoprint_astroprint.db")

		self.cameraManager = cameraManager(self)
		self.astroprintCloud = AstroprintCloud(self)
		self.cameraManager.astroprintCloud = self.astroprintCloud
		self.materialCounter = MaterialCounter(self)

	def onLogout(self):
		self.send_event("userLoggedOut", True)

	def onLogin(self):
		self.send_event("userLogged", True)

	def on_shutdown(self):
		#clear al process we created
		self.cameraManager.shutdown()
		self.astroprintCloud.downloadmanager.shutdown()
		self.unregister_printer_listener()

	def get_logger(self):
		return self._logger

	def get_printer(self):
		return self._printer

	def get_printer_listener(self):
		return self._printerListener

	def get_settings(self):
		return self._settings

	def get_plugin_version(self):
		return self._plugin_version

	def get_file_manager(self):
		return self._file_manager

	def sendSocketInfo(self):
		data = {
			'heatingUp' : self.printerIsHeating(),
			'currentLayer' : self._printerListener.get_current_layer() if self._printerListener else None,
			'camera' : self.cameraManager.cameraActive if self.cameraManager else None,
			'userLogged' : self.user['email'] if self.user else None,
			'job' : self._printerListener.get_job_data() if self._printerListener else None
		}
		self.send_event("socketUpdate", data)

	def astroPrintUserLoggedOut(self):
		self.send_event("astroPrintUserLoggedOut")

	def send_event(self, event, data=None):
		event = {'event':event, 'data':data}
		self._plugin_manager.send_plugin_message(self._plugin_name, event)

	def get_settings_defaults(self):

		appSite ="https://cloud.astroprint.com"
		appId="c4f4a98519194176842567680239a4c3"
		apiHost="https://api.astroprint.com/v2"
		webSocket="wss://boxrouter.astroprint.com"
		product_variant_id = "9e33c7a4303348e0b08714066bcc2750"
		boxName = socket.gethostname()


		return dict(
			#AstroPrintEndPoint
			appSite = appSite,
			appId = appId,
			apiHost = apiHost,
			webSocket = webSocket,
			product_variant_id = product_variant_id,
			boxName = boxName,
			printerModel = {'id' : None, 'name' : None},
			filament = {'name' : None, 'color' : None},
			camera = False,
			#Adittional printer settings
			max_nozzle_temp = 280, #only for being set by AstroPrintCloud, it wont affect octoprint settings
			max_bed_temp = 140,
		)

	def get_template_vars(self):

		return dict(appSite = self._settings.get(["appSite"]),
					appId = self._settings.get(["appId"]),
					appiHost = self._settings.get(["apiHost"]),
					boxName = self._settings.get(["boxName"]),
					printerModel = json.dumps(self._settings.get(["printerModel"])) if self._settings.get(["printerModel"])['id'] else "null",
					filament = json.dumps(self._settings.get(["filament"])) if self._settings.get(["filament"])['name'] else "null",
					user = json.dumps({'name': self.user['name'], 'email': self.user['email']}, cls=JsonEncoder, indent=4) if self.user else None ,
					camera = self._settings.get(["camera"])
					)


	def get_template_configs(self):
		return [
			dict(type="navbar", custom_bindings=False),
			dict(type="settings", custom_bindings=True)
		]

	##~~ AssetPlugin mixin

	def get_assets(self):
		# Define your plugin's asset files to automatically include in the
		# core UI here.
		return dict(
			js=["js/astroprint.js"],
			css=["css/astroprint.css"],
			less=["less/astroprint.less"]
		)

	##~~ Softwareupdate hook

	def get_update_information(self):
		# Define the configuration for your plugin to use with the Software Update
		# Plugin here. See https://github.com/foosel/OctoPrint/wiki/Plugin:-Software-Update
		# for details.
		return dict(
			astroprint=dict(
				displayName="AstroPrint",
				displayVersion=self._plugin_version,

				# version check: github repository
				type="github_release",
				user="AstroPrint",
				repo="OctoPrint-AstroPrint",
				current=self._plugin_version,

				# update method: pip
				pip="https://github.com/AstroPrint/OctoPrint-AstroPrint/archive/{target_version}.zip"
			)
		)

	def register_printer_listener(self):
		self._printerListener = PrinterListener(self)
		self._printer.register_callback(self._printerListener)

	def unregister_printer_listener(self):
		self._printer.unregister_callback(self._printerListener)
		self._printerListener = None

	def on_event(self, event, payload):

		printEvents = [
			Events.CONNECTED,
			Events.DISCONNECTED,
			Events.PRINT_STARTED,
			Events.PRINT_DONE,
			Events.PRINT_FAILED,
			Events.PRINT_CANCELLED,
			Events.PRINT_PAUSED,
			Events.PRINT_RESUMED,
			Events.ERROR,
			Events.TOOL_CHANGE
		]

		cameraSuccessEvents = [
			Events.CAPTURE_DONE,
			Events.POSTROLL_END,
			Events.MOVIE_RENDERING,
			Events.MOVIE_DONE,
		]

		cameraFailEvents = [
			Events.CAPTURE_FAILED,
			Events.MOVIE_FAILED
		]

		if event in cameraSuccessEvents:
			self.cameraManager.cameraConnected()

		elif event in cameraFailEvents:
			self.cameraManager.cameraError()

		elif event == Events.FILE_REMOVED:
			if payload['storage'] == 'local':
				self.astroprintCloud.db.deletePrintFile(payload['path'])

		elif event == Events.CONNECTED:
			self.send_event("canPrint", True)

		elif event == Events.PRINT_CANCELLED or event == Events.PRINT_FAILED:
			self.send_event("canPrint", True)
			if self.user and self.astroprintCloud.currentlyPrinting:
				self.astroprintCloud.updatePrintJob("failed", self.materialCounter.totalConsumedFilament)
			self.astroprintCloud.currentlyPrinting = None
			self.cameraManager.stop_timelapse()
			self._analyzed_job_layers = None

		elif event == Events.PRINT_DONE:
			if self.user and self.astroprintCloud.currentlyPrinting:
				self.astroprintCloud.updatePrintJob("success", self.materialCounter.totalConsumedFilament)
			self.astroprintCloud.currentlyPrinting = None
			self.cameraManager.stop_timelapse()
			self.send_event("canPrint", True)

		elif event == Events.PRINT_STARTED:
			self.send_event("canPrint", False)
			if self.user:
				self.astroprintCloud.printStarted(payload['name'], payload['path'])

			self.materialCounter.startPrint()
			self._printerListener.startPrint(payload['file'])
		if  event in printEvents:
			self.sendSocketInfo()
			if self.user and self.astroprintCloud:
				self.astroprintCloud.sendCurrentData()

		return

	def printerIsHeating(self):
		heating = False
		if self._printer.is_operational():
			heating = self._printer._comm._heating

		return heating

	def currentTool(self):
		tool = None
		if self._printer.is_operational():
			tool = self._printer._comm._currentTool

		return tool

	def count_material(self, comm_instance, phase, cmd, cmd_type, gcode, *args, **kwargs):
		if self.materialCounter:
			if (gcode):
				gcodeHandler = "_gcode_" + gcode
				if hasattr(self.materialCounter, gcodeHandler):
					materialCounter = getattr(self.materialCounter, gcodeHandler,None)
					materialCounter(cmd)


	def is_blueprint_protected(self):
		return False

	@octoprint.plugin.BlueprintPlugin.route("/login", methods=["POST"])
	@admin_permission.require(403)
	def login(self):
		return self.astroprintCloud.loginAstroPrint(
            request.json['code'],
            request.json['url'],
            request.json['ap_access_key']
        )

	@octoprint.plugin.BlueprintPlugin.route("/logout", methods=["POST"])
	@admin_permission.require(403)
	def logout(self):
		return self.astroprintCloud.logoutAstroPrint()


	@octoprint.plugin.BlueprintPlugin.route("/designs", methods=["GET"])
	@admin_permission.require(403)
	def getDesigns(self):
		return self.astroprintCloud.getDesigns()

	@octoprint.plugin.BlueprintPlugin.route("/printfiles", methods=["GET"])
	@admin_permission.require(403)
	def getPrintFiles(self):
		designId = request.args.get('designId', None)
		return self.astroprintCloud.getPrintFiles(designId)

	@octoprint.plugin.BlueprintPlugin.route("/downloadDesign", methods=["POST"])
	@admin_permission.require(403)
	def downloadDesign(self):
		designId = request.json['designId']
		name = request.json['name']
		return self.astroprintCloud.getDesignDownloadUrl(designId, name)

	@octoprint.plugin.BlueprintPlugin.route("/downloadPrintFile", methods=["POST"])
	@admin_permission.require(403)
	def downloadPrintFile(self):
		printFileId = request.json['printFileId']
		printNow = request.json['printNow']
		if self.astroprintCloud.printFile(printFileId, printNow) == "print":
			return jsonify({"state" : "printing"}), 200, {'ContentType':'application/json'}
		if self.astroprintCloud.printFile(printFileId, printNow) == "download":
			return jsonify({"state" : "downloading"}), 200, {'ContentType':'application/json'}
		return jsonify({'error': "Internal server error"}), 500, {'ContentType':'application/json'}

	@octoprint.plugin.BlueprintPlugin.route("/canceldownload", methods=["POST"])
	@admin_permission.require(403)
	def canceldownload(self):
		id = request.json['id']
		self.astroprintCloud.downloadmanager.cancelDownload(id)
		return jsonify({"success" : True }), 200, {'ContentType':'application/json'}

	@octoprint.plugin.BlueprintPlugin.route("/checkcamerastatus", methods=["GET"])
	@admin_permission.require(403)
	def checkcamerastatus(self):
		self.cameraManager.checkCameraStatus()
		return jsonify({"connected" : True if self.cameraManager.cameraActive else False }), 200, {'ContentType':'application/json'}

	@octoprint.plugin.BlueprintPlugin.route("/isloggeduser", methods=["GET"])
	@admin_permission.require(403)
	def isloggeduser(self):
		if self.user:
			return jsonify({"user" : {"name" : self.user['name'], "email" : self.user['email']}}), 200, {'ContentType':'application/json'}
		else:
			return jsonify({"user" : False }), 200, {'ContentType':'application/json'}

	@octoprint.plugin.BlueprintPlugin.route("/iscameraconnected", methods=["GET"])
	@admin_permission.require(403)
	def iscameraconnected(self):
		return jsonify({"connected" : True if self.cameraManager.cameraActive else False }), 200, {'ContentType':'application/json'}

	@octoprint.plugin.BlueprintPlugin.route("/connectboxrouter", methods=["POST"])
	@admin_permission.require(403)
	def connectboxrouter(self):
		if self.astroprintCloud and self.astroprintCloud.bm:
			self.astroprintCloud.bm.boxrouter_connect()
		return jsonify({"connecting" : True }), 200, {'ContentType':'application/json'}

	@octoprint.plugin.BlueprintPlugin.route("/initialstate", methods=["GET"])
	@admin_permission.require(403)
	def initialstate(self):
		return jsonify({
					"user" : {"name" : self.user['name'], "email" : self.user['email']} if self.user else False,
					"connected" : True if self.cameraManager.cameraActive else False,
					"can_print" : True if self._printer.is_operational() and not (self._printer.is_paused() or self._printer.is_printing()) else False,
					"boxrouter_status" : self.astroprintCloud.bm.status if self.astroprintCloud and self.astroprintCloud.bm else "disconnected"
					}), 200, {'ContentType':'application/json'}

	@octoprint.plugin.BlueprintPlugin.route("/changename", methods=["POST"])
	@admin_permission.require(403)
	def changeboxroutername(self):
		name = request.json['name']
		self._settings.set(['boxName'], name)
		self._settings.save()
		if self.astroprintCloud and self.astroprintCloud.bm:
			data = {
				"name": name
			}
			return self.astroprintCloud.updateBoxrouterData(data)
		else:
			return jsonify({"connecting" : True }), 200, {'ContentType':'application/json'}

	@octoprint.plugin.BlueprintPlugin.route("/manufactures", methods=["GET"])
	@admin_permission.require(403)
	def getManufacturers(self):
		return self.astroprintCloud.getManufacturer()

	@octoprint.plugin.BlueprintPlugin.route("/manufacturermodels", methods=["GET"])
	@admin_permission.require(403)
	def getManufacturerModels(self):
		manufacturerId = request.args.get('manufacturerId', None)
		return self.astroprintCloud.getManufacturerModels(manufacturerId)

	@octoprint.plugin.BlueprintPlugin.route("/manufacturermodelinfo", methods=["GET"])
	@admin_permission.require(403)
	def getModelInfo(self):
		modelId = request.args.get('modelId', None)
		return self.astroprintCloud.getPrintFiles(modelId)

	@octoprint.plugin.BlueprintPlugin.route("/changeprinter", methods=["POST"])
	@admin_permission.require(403)
	def changeprinter(self):
		printer = request.json['printerModel']
		self._settings.set(['printerModel'], printer)
		self._settings.save()
		data = {
			"printerModel": printer
		}
		return self.astroprintCloud.updateBoxrouterData(data)

	@octoprint.plugin.BlueprintPlugin.route("/changeprinter", methods=["DELETE"])
	@admin_permission.require(403)
	def deleteprinter(self):
		self._settings.set(['printerModel'], {'id' : None, 'name' : None})
		self._settings.save()
		data = {
			"printerModel": None
		}
		return self.astroprintCloud.updateBoxrouterData(data)

	@octoprint.plugin.BlueprintPlugin.route("/changefilament", methods=["POST"])
	@admin_permission.require(403)
	def changefilament(self):
		filament = request.json['filament']
		self._settings.set(['filament'], filament)
		self._settings.save()
		self.astroprintCloud.bm.triggerEvent('filamentChanged', {'filament' : filament})
		return jsonify({"Filament updated" : True }), 200, {'ContentType':'application/json'}

	@octoprint.plugin.BlueprintPlugin.route("/changefilament", methods=["DELETE"])
	@admin_permission.require(403)
	def removefilament(self):
		self._settings.set(['filament'], {'name' : None, 'color' : None})
		self._settings.save()
		self.astroprintCloud.bm.triggerEvent('filamentChanged', {'filament' : {'name' : None, 'color' : None}})
		return jsonify({"Filament removed" : True }), 200, {'ContentType':'application/json'}

	##LOCAL AREA
	#Functions related to local aspects

	@octoprint.plugin.BlueprintPlugin.route("/astrobox/identify", methods=["GET"])
	def identify(self):
		if not self.astroprintCloud or not self.astroprintCloud.bm:
			abort(503)
		return Response(json.dumps({
			'id': self.astroprintCloud.bm.boxId,
			'name': self._settings.get(["boxName"]),
			'version': self._plugin_version,
			'firstRun': True if self._settings.global_get_boolean(["server", "firstRun"]) else None,
			'online': True,
		})
		)

	@octoprint.plugin.BlueprintPlugin.route("/accessKeys", methods=["POST"])
	def getAccessKeys(self):
		email = request.values.get('email', None)
		accessKey = request.values.get('accessKey', None)

		if not email or not accessKey:
			abort(401) # wouldn't a 400 make more sense here?

		if self.user and self.user['email'] == email and self.user['accessKey'] == accessKey and self.user['id']:
			# only respond positively if we have an AstroPrint user and their mail AND accessKey match AND
			# they also have a valid id
			return jsonify(api_key=self._settings.global_get(["api", "key"]),
								ws_token=create_ws_token(self.user['id']))

		if not self.user:
			abort (401)
		# everyone else gets the cold shoulder
		abort(403)

	@octoprint.plugin.BlueprintPlugin.route("/status", methods=["GET"])
	@admin_permission.require(403)
	def getStatus(self):

		fileName = None

		if self._printer.is_printing():
			currentJob = self._printer.get_current_job()
			fileName = currentJob["file"]["name"]

		return Response(
			json.dumps({
				'id': self.astroprintCloud.bm.boxId,
				'name': self._settings.get(["boxName"]),
				'printing': self._printer.is_printing(),
				'fileName': fileName,
				'printerModel': self._settings.get(["printerModel"]) if self._settings.get(['printerModel'])['id']  else None,
				'filament' : self._settings.get(["filament"]),
				'material': None,
				'operational': self._printer.is_operational(),
				'paused': self._printer.is_paused(),
				'camera': True, #self.cameraManager.cameraActive,
				'remotePrint': True,
				'capabilities': ['remotePrint', 'multiExtruders', 'allowPrintFile'] + self.cameraManager.capabilities
			}),
			mimetype= 'application/json'
		)

	@octoprint.plugin.BlueprintPlugin.route("/api/printer-profile", methods=["GET"])
	@admin_permission.require(403)
	def printer_profile_patch(self):
		printerProfile = self._printer_profile_manager.get_current_or_default()
		profile = {
			'driver': "marlin", #At the moment octopi only supports marlin
			'extruder_count': printerProfile['extruder']['count'],
			'max_nozzle_temp': self._settings.get(["max_nozzle_temp"]),
			'max_bed_temp': self._settings.get(["max_bed_temp"]),
			'heated_bed': printerProfile['heatedBed'],
			'cancel_gcode': ['G28 X0 Y0'],#ToDo figure out how to get it from snipet
			'invert_z': printerProfile['axes']['z']['inverted'],
			'printerModel': self._settings.get(["printerModel"]) if self._settings.get(['printerModel'])['id']  else None,
			'filament' : self._settings.get(["filament"])
		}
		return jsonify(profile)

	@octoprint.plugin.BlueprintPlugin.route('/api/astroprint', methods=['DELETE'])
	@admin_permission.require(403)
	def astroPrint_logout(self):
		return self.astroprintCloud.logoutAstroPrint()

	@octoprint.plugin.BlueprintPlugin.route('/api/job', methods=['GET'])
	@admin_permission.require(403)
	def jobState(self):
		currentData = self._printer.get_current_data()
		return jsonify({
			"job": currentData["job"],
			"progress": currentData["progress"],
			"state": currentData["state"]["text"]
		})

# If you want your plugin to be registered within OctoPrint under a different name than what you defined in setup.py
# ("OctoPrint-PluginSkeleton"), you may define that here. Same goes for the other metadata derived from setup.py that
# can be overwritten via __plugin_xyz__ control properties. See the documentation for that.
__plugin_name__ = "AstroPrint"

def __plugin_load__():
	global __plugin_implementation__
	__plugin_implementation__ = AstroprintPlugin()

	global __plugin_hooks__
	__plugin_hooks__ = {
		"octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information,
		"octoprint.comm.protocol.gcode.sent": __plugin_implementation__.count_material
	}
