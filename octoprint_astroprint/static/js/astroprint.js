/*
 * View model for OctoPrint-AstroPrint
 *
 * Author: AstroPrint Product Team
 * License: AGPLv3
 * Copyright: 2017 3DaGoGo Inc.
 */

var astroPrintPluginStarted = false;

$(function () {

    function AstroprintViewModel(parameters) {

        var self = this;
        self.settings = parameters[0];
        self.loginState = parameters[1];
        self.astroprintUser = ko.observable(null) //null while views are being rendered
        self.designList = ko.observable([]);
        self.manufacturesList = ko.observable([]);
        self.printFileList = ko.observable([]);
        self.filter = ko.observable("");
        self.boxrouter_status = ko.observable();
        self.changeNameDialog = undefined;
        self.isOctoprintAdmin = ko.observable(self.loginState.isAdmin());
        self.subject = ko.observable("");
        self.description = ko.observable("");
        self.access_key = ko.observable("");
        self.boxName = ko.observable(astroprint_variables.boxName);
        self.printerModel = ko.observable(astroprint_variables.printerModel)
        self.cacheBoxName = ko.observable(self.boxName());

        //filter Designs
        self.filteredDesigns = ko.computed(function () {
            if (!self.filter()) {
                return self.designList();
            } else {
                return ko.utils.arrayFilter(self.designList(), function (design) {
                    return design.name.indexOf(self.filter()) >= 0
                });
            }
        });


        // Design Pagination
        self.designsPerPage = 5; //lets show 5 design per page

        self.totalPages = ko.computed(function () {
            var pages = Math.floor(self.filteredDesigns().length / self.designsPerPage);
            pages += self.filteredDesigns().length % self.designsPerPage > 0 ? 1 : 0;
            return pages > 0 ? pages : 0
        });

        self.currentPage = ko.observable(0);

        self.filteredCurrentPage = ko.computed(function () {
            if (self.totalPages() <= self.currentPage()) {
                self.currentPage(self.totalPages());
                return self.currentPage();
            }
            if (!self.currentPage()) {
                self.currentPage(0)
            }
            return self.currentPage()
        });

        self.indexPagesToShow = ko.computed(function () {
            var limitPageNumber = 5
            var start = Math.max((self.filteredCurrentPage() - Math.floor(limitPageNumber / 2)), 1);
            var minDesviation = (self.filteredCurrentPage() - Math.floor(limitPageNumber / 2)) > 0 ? 0 : Math.ceil(limitPageNumber / 2) - self.filteredCurrentPage()
            var end = Math.min((self.filteredCurrentPage() + (Math.floor(limitPageNumber / 2) + minDesviation)), self.totalPages())
            var maxDesviation = self.totalPages() - (self.filteredCurrentPage() + Math.floor(limitPageNumber / 2) + minDesviation) >= 0 ? 0 : (Math.floor(limitPageNumber / 2) - (self.totalPages() - self.filteredCurrentPage()))
            start = Math.max((self.filteredCurrentPage() - (Math.floor(limitPageNumber / 2) + maxDesviation)), 1);
            if (end < 1) {
                return ko.observable(Array(1 - start + 1).fill(start).map((a, b) => { return a + b }).filter(i => i >= start))
            }
            return ko.observable(Array(end - start + 1).fill(start).map((a, b) => { return a + b }).filter(i => i >= start))
        })

        self.changePage = function (page) {
            self.currentPage(page - 1)
        }

        self.designs = ko.computed(function () {
            var first = self.currentPage() * self.designsPerPage;
            return (self.filteredDesigns().slice(first, first + self.designsPerPage));
        });

        self.firstPage = function () {
            self.currentPage(0);
        }

        self.prevPage = function () {
            if (self.currentPage() > 0) {
                self.currentPage(self.currentPage() - 1);
            }
        }

        self.nextPage = function () {
            if (self.currentPage() < (self.totalPages() - 1)) {
                self.currentPage(self.currentPage() + 1);
            }
        }

        self.lastPage = function () {
            self.currentPage(self.totalPages() - 1);
        }


        //filter PrintFiles
        self.filteredPrintFiles = ko.computed(function () {
            if (!self.filter()) {
                return self.printFileList();
            } else {
                return ko.utils.arrayFilter(self.printFileList(), function (printFile) {
                    return printFile.filename.indexOf(self.filter()) >= 0
                });
            }
        });

         // PrintFile Pagination
         self.printFilePerPage = 5; //lets show 5 printFiles per page

         self.totalPrintFilePage = ko.computed(function () {
             var pages = Math.floor(self.filteredPrintFiles().length / self.printFilePerPage);
             pages += self.filteredPrintFiles().length % self.printFilePerPage > 0 ? 1 : 0;
             return pages > 0 ? pages : 0
         });

         self.currentPrintFilePage = ko.observable(0);

         self.filteredCurrentPrintFilePage = ko.computed(function () {
             if (self.totalPrintFilePage() <= self.currentPrintFilePage()) {
                 self.currentPrintFilePage(self.totalPrintFilePage());
                 return self.currentPrintFilePage();
             }
             if (!self.currentPrintFilePage()) {
                 self.currentPrintFilePage(0)
             }
             return self.currentPrintFilePage()
         });

         self.indexPrintFilePagesToShow = ko.computed(function () {
             var limitPageNumber = 5
             var start = Math.max((self.filteredCurrentPrintFilePage() - Math.floor(limitPageNumber / 2)), 1);
             var minDesviation = (self.filteredCurrentPrintFilePage() - Math.floor(limitPageNumber / 2)) > 0 ? 0 : Math.ceil(limitPageNumber / 2) - self.filteredCurrentPrintFilePage()
             var end = Math.min((self.filteredCurrentPrintFilePage() + (Math.floor(limitPageNumber / 2) + minDesviation)), self.totalPrintFilePage())
             var maxDesviation = self.totalPrintFilePage() - (self.filteredCurrentPrintFilePage() + Math.floor(limitPageNumber / 2) + minDesviation) >= 0 ? 0 : (Math.floor(limitPageNumber / 2) - (self.totalPrintFilePage() - self.filteredCurrentPrintFilePage()))
             start = Math.max((self.filteredCurrentPrintFilePage() - (Math.floor(limitPageNumber / 2) + maxDesviation)), 1);
             if (end < 1) {
                 return ko.observable(Array(1 - start + 1).fill(start).map((a, b) => { return a + b }).filter(i => i >= start))
             }
             return ko.observable(Array(end - start + 1).fill(start).map((a, b) => { return a + b }).filter(i => i >= start))
         })

         self.changePrintFilePage = function (page) {
             self.currentPrintFilePage(page - 1)
         }

         self.printFiles = ko.computed(function () {
             var first = self.currentPrintFilePage() * self.printFilePerPage;
             return (self.filteredPrintFiles().slice(first, first + self.printFilePerPage));
         });

         self.firstPrintFilePage = function () {
             self.currentPrintFilePage(0);
         }

         self.prevPrintFilePage = function () {
             if (self.currentPrintFilePage() > 0) {
                 self.currentPrintFilePage(self.currentPrintFilePage() - 1);
             }
         }

         self.nextPrintFilePage = function () {
             if (self.currentPrintFilePage() < (self.totalPrintFilePage() - 1)) {
                 self.currentPrintFilePage(self.currentPrintFilePage() + 1);
             }
         }

         self.lastPrintFilePage = function () {
             self.currentPrintFilePage(self.totalPrintFilePage() - 1);
         }

        self.designsRetrieved = ko.observable("loading") //values: loading, done, error
        self.printFilesRetrieved = ko.observable("loading") //values: loading, done, error
        self.currentUrl = window.location.href.split('?')[0];
        self.cam_status = ko.observable('loading') //null while refreshing state
        self.can_print = ko.observable(false)
        self.downloading = ko.observable(false)
        self.downloadDialog = ko.observable(new DownloadDialog) //even if serrver side can support multiple downloads, we will restric client side to just one
        self.progress = ko.observable(0)

        //DownlaodDialog model
        function DownloadDialog() {
            var self = this;
            self.id = ko.observable(null);
            self.name = ko.observable(null);
            self.image = ko.observable(null);
            self.progress = ko.observable(0);
            self.failed = ko.observable(false);
            self.downloading = ko.observable(false);
            self.file = null;
            self.fileType = null;

            self.downloadStarted = function (id, name, image, file) {
                self.id(id);
                self.name(name);
                self.image(image)
                self.progress(0);
                self.failed(false);
                self.downloading(true);
                self.file = file
            }

            self.cancelDownload = function () {
                if (self.progress() < 100) {
                    $.ajax({
                        type: "POST",
                        contentType: "application/json; charset=utf-8",
                        url: PLUGIN_BASEURL + "astroprint/canceldownload",
                        data: JSON.stringify({ 'id': self.id() }),
                        dataType: "json",
                        success: function (success) {
                            self.downloading(false);
                            self.file.downloading(false);
                            self.progress(0);
                        },
                        error: function (error) {
                            console.error("Download couldn´t be canceled");
                        }
                    });
                }
            }

            self.uploadProgress = function (id, progress) {
                if (!self.failed() && id == self.id() && self.progress() != 100) {
                    self.progress(progress);
                    if (self.progress() == 100) {
                        if (self.file.format) {
                            new PNotify({
                                title: gettext("File Downloaded"),
                                text: gettext("Your AstroPrint Cloud print file:" + self.name() + ", was added to your files."),
                                type: "success"
                            });
                        } else {
                            new PNotify({
                                title: gettext("File Downloaded"),
                                text: gettext("Your AstroPrint Cloud design:" + self.name() + ", was added to your files."),
                                type: "success"
                            });
                        }
                        self.downloading(false);
                        self.file.downloading(false);
                        self.progress(0);
                    }
                }
            }

            self.downloadFailed = function (id, message) {
                if (id == self.id) {
                    self.failed(message)
                    self.downloading(false)
                    self.file.downloading(false);
                }
            }

            self.closeDialog = function () {
                if (self.downloading() || self.failed()) {
                    self.id(null);
                    self.name(null);
                    self.progress(0);
                    self.failed(false);
                    self.downloading(false);
                }
            }
        }


        //Manufacture model
        function Manufacturer(id, name, printerCount) {
            var self = this;
            self.id = id;
            self.name = name;
            self.printerCount = printerCount
            self.loading = ko.observable(true);
            self.manufacturerModels = ko.observable()
            self.getModels = function(){
                if(!self.manufacturerModels() && self.printerCount > 0){
                    $.ajax({
                        type: "GET",
                        contentType: "application/json; charset=utf-8",
                        url: PLUGIN_BASEURL + "astroprint/manufacturermodels",
                        data: {
                            manufacturerId: self.id
                        },
                        success: function (data) {
                            var manufacturerModels = [];
                            for (var model of data.data) {
                                manufacturerModels.push(
                                    new PrinterModel(model.id, model.name, model.printer_count)
                                );
                            }
                            self.loading(false)
                            self.manufacturerModels(manufacturerModels);
                        },
                        error: function () {
                            new PNotify({
                                title: gettext("Error retrievind manufacturers models"),
                                text: gettext("There was an error retrieving AstroPrint models, please try again later."),
                                type: "error"
                            });
                        },
                        dataType: "json"
                    });
                }
            }
        }

        self.selectManufacturer = function()
        {
            self.selectedManufactured().getModels()
        }

        self.selectManufacturerModel = function()
        {
        }

        self.selectedManufactured =  ko.observable();
        self.selectedManufacturedModel = ko.observable();
        self.changingPrinter = ko.observable(false)

        self.getManufacturers = function () {
            $.ajax({
                type: "GET",
                contentType: "application/json; charset=utf-8",
                url: PLUGIN_BASEURL + "astroprint/manufactures",
                start_time: new Date().getTime(),
                success: function (data) {
                    var manufactures = [];
                    for (var manufacture of data.data) {
                        manufactures.push(
                            new Manufacturer(manufacture.id, manufacture.name, manufacture.printer_count)
                        );
                    }
                    self.manufacturesList(manufactures);
                },
                error: function () {
                    new PNotify({
                        title: gettext("Error retrievind manufacturers information"),
                        text: gettext("There was an error retrieving AstroPrint manufacturers, please try again later."),
                        type: "error"
                    });
                },
                dataType: "json"
            });
        }

        //Printer Manufacturer model
        function PrinterModel(id, name) {
            var self = this;
            self.id = id;
            self.name = name;
            self.config = ko.observable();
            self.start_commands = ko.observable(null);
            self.end_commands = ko.observable(null);
            self.slicer = ko.observable(null);
            self.format = ko.observable(null);
            self.setModelInfo = function (config, start_commands, end_commands, slicer, format){
                self.config(config);
                self.start_commands(start_commands);
                self.end_commands(end_commands);
                self.slicer(slicer);
                self.format(format);
            }
        }

        self.changePrinter = function (){
            self.changingPrinter(true)
            let printerModel = { 'id': self.selectedManufacturedModel().id, name : self.selectedManufacturedModel().name}
            $.ajax({
                type: "POST",
                contentType: "application/json; charset=utf-8",
                url: PLUGIN_BASEURL + "astroprint/changeprinter",
                data: JSON.stringify({printerModel : printerModel}),
                dataType: "json",
                success: function () {
                    self.printerModel(printerModel);
                    self.changingPrinter(false)
                    $('#changePrinterModel').modal('hide');
                },
                error: function (error) {
                    self.changingPrinter(false)
                    console.error(error)
                }
            });
        }

        self.removePrinter = function (){
            self.changingPrinter(true)
            $.ajax({
                type: "DELETE",
                contentType: "application/json; charset=utf-8",
                url: PLUGIN_BASEURL + "astroprint/changeprinter",
                dataType: "json",
                success: function () {
                    self.printerModel(null);
                    self.changingPrinter(false)
                    $('#removePrinterModel').modal('hide');
                },
                error: function (error) {
                    self.changingPrinter(false)
                    console.error(error)
                }
            });
        }

        self.filamentModel =  ko.observable(astroprint_variables.filament)
        self.filamentName = ko.observable("")
        self.filamentColor = ko.observable("#000000")
        self.changingFilament = ko.observable(false)
        self.colors = ko.observableArray([
        "#f05251", //RED
        "#FF872B", //ORANGE
        "#FFD54C", //YELLOW
        "#59cd90", //GREEN
        "#00bef5", //BLUE
        "#435FEF", //DARKBLUE
        "#A25ADD", //PURPLE
        "#EF7587", //PINK OR CORAL
        "#f7f7f7", //WHITE
        "#889192", //SILVER
        "#BA915D", //BROWN
        "#333333",  //BLACK
        ])

        if(self.filamentModel()){
            self.filamentName(self.filamentModel().name)
            self.filamentColor(self.filamentModel().color)
        }

        self.selectFilamentColor = function() {
            self.filamentColor(this.valueOf());
        }

        self.changeFilament = function (){
            self.changingFilament(true)
            let filament = { name: self.filamentName(), color : self.filamentColor()}
            $.ajax({
                type: "POST",
                contentType: "application/json; charset=utf-8",
                url: PLUGIN_BASEURL + "astroprint/changefilament",
                data: JSON.stringify({filament : filament}),
                dataType: "json",
                success: function () {
                    self.filamentModel(filament);
                    self.changingFilament(false)
                    $('#changeFilament').modal('hide');
                },
                error: function (error) {
                    self.changingPrinter(false)
                    console.error(error)
                }
            });
        }

        self.removeFilament = function (){
            self.changingFilament(true)
            $.ajax({
                type: "DELETE",
                contentType: "application/json; charset=utf-8",
                url: PLUGIN_BASEURL + "astroprint/changefilament",
                dataType: "json",
                success: function () {
                    self.filamentModel(null);
                    self.changingFilament(false)
                    $('#removeFilamentModel').modal('hide');
                },
                error: function (error) {
                    self.changingPrinter(false)
                    console.error(error)
                }
            });
        }

        //Design model
        function Design(id, name, image, printFilesCount, allow_download) {
            var self = this;
            self.id = id;
            self.name = name;
            self.printFilesCount = ko.observable(printFilesCount);
            self.image = ko.observable("http:" + image);
            self.printFiles = ko.observableArray([]);
            self.allow_download = ko.observable(allow_download);
            self.expanded = ko.observable(false);
            self.loadingPrintfiles = ko.observable(false);
            self.downloading = ko.observable(false); //values: false, 'downloading', 'error',
        }

        //PrintFile model
        function PrintFile(id, created, filename, image, info, format, printer, material, quality) {
            var self = this;
            self.id = id;
            self.created = moment().add(created + "Z").format("DD MMM YYYY (h:mmA)");
            self.filename = filename;
            self.image = image;
            self.sizeX = null
            self.sizeY = null
            self.sizeZ = null
            self.print_time = null
            self.layer_height = null
            self.layer_count = null;
            self.filament_length = null
            self.filament_volume = null
            self.filament_weight = null
            self.total_filament = null

            if(info){
                self.sizeX = Math.round(Number(info.sizeX) * 100) / 100;
                self.sizeY = Math.round(Number(info.sizeY) * 100) / 100;
                self.sizeZ = Math.round(Number(info.sizeZ) * 100) / 100;
                var seconds = Number(info.print_time);
                var hours = Math.floor(seconds / 3600);
                var minutes = Math.floor(seconds % 3600 / 60);
                seconds = Math.floor(seconds % 3600 % 60);
                self.print_time = ((hours > 0 ? hours + ":" + (minutes < 10 ? "0" : "") : "") + minutes + ":" + (seconds < 10 ? "0" : "") + seconds);
                self.layer_height = info.layer_height;
                self.layer_count = info.layer_count;
                self.filament_length = Math.round(Number(info.filament_length / 10) * 100) / 100;
                self.filament_volume = Math.round(Number(info.filament_volume / 1000) * 100) / 100;
                if(material){
                    self.filament_weight =  Math.round((self.filament_volume * 0.001 * material.density) * 100) / 100;
                }
                self.total_filament = info.total_filament;
            }

            self.format = format;
            self.printer = printer ? printer.name : null;
            self.material = material ? material.name : null;
            self.quality = quality;
            self.expanded = ko.observable(false);
            self.downloading = ko.observable(false);
        }

        /* Event handler */
        self.onDataUpdaterPluginMessage = function (plugin, message) {
            if (plugin == "AstroPrint") {
                switch (message.event) {
                    case "cameraStatus":
                        self.changeCameraStatus(message.data);
                        break;
                    case "logOut":
                        self.logOut()
                        break;
                    case "canPrint":
                        self.can_print(message.data)
                        break;
                    case "download":
                        if (message.data.progress) {
                            self.downloadDialog().uploadProgress(message.data.id, message.data.progress)
                        }
                        if (message.data.failed) {
                            self.downloadDialog().downloadFailed(message.data.id, message.data.failed)
                        }
                        break;
                    case "userLogged":
                        if (!self.isOctoprintAdmin()) {
                            var logTries = 5; //handle asyncronous login state from octoprint
                            self.userLogged(logTries);
                        }
                        break;
                    case "userLoggedOut":
                        if (self.isOctoprintAdmin()) {
                            var logOutTries = 5;
                            self.userLoggedOut(logOutTries);
                        }
                        break;
                    case "astroPrintUserLoggedOut":
                        if(self.astroprintUser()){
                            self.astroprintUser(false);
                        }
                    case "boxrouterStatus":
                        self.boxrouterStatusChange(message.data)
                    default:
                        break;
                }
            }
        }

        self.boxrouterStatusChange = function (state){
            self.boxrouter_status(state)
            switch (state){
                case "error":
                    new PNotify({
                        title: gettext("Boxrouter error"),
                        text: gettext("There was an error connecting your boxrouter to AstroPrint, please try again later."),
                        type: "error"
                    });
                case "connected":
                    self.changingname(false)
                    self.changeNameDialog.modal('hide')
                    new PNotify({
                        title: gettext("AstroPrint Boxrouter Connected"),
                        text: gettext("Your octopi is connected to Astroprint cloud"),
                        type: "success"
                    });
            }
        }

        self.connectBoxrouter = function (){
            $.ajax({
                type: "POST",
                contentType: "application/json; charset=utf-8",
                url: PLUGIN_BASEURL + "astroprint/connectboxrouter",
                succes : function (data){
                }
            })
        }

        self.userLogged = function (logTries) {
            setTimeout(function () {
                logTries--;
                if (self.loginState.isAdmin() && !self.isOctoprintAdmin()) {
                    astroPrintPluginStarted = false
                    $("#startingUpPlugin").show();
                    $("#noAstroprintLogged").hide();
                    $("#astroPrintLogged").hide();
                    self.isOctoprintAdmin(self.loginState.isAdmin());
                    self.initialice_variables();
                } else if (logTries > 0 && !self.isOctoprintAdmin()) {
                    self.userLogged(logTries);
                }
            }, 500)
        }

        self.userLoggedOut = function (logOutTries) {
            logOutTries--;
            setTimeout(function () {
                if (!self.loginState.isAdmin() && self.isOctoprintAdmin()) {
                    self.isOctoprintAdmin(self.loginState.isAdmin());
                    self.astroprintUser(null);
                    self.designList([]);
                    self.printFileList([]);
                } else if (logOutTries > 0 && self.isOctoprintAdmin()) {
                    self.userLoggedOut(logOutTries);
                }
            }, 500)
        }

        /*  Initialice variables  */
        self.initialice_variables = function () {
            $.ajax({
                type: "GET",
                contentType: "application/json; charset=utf-8",
                url: PLUGIN_BASEURL + "astroprint/initialstate",
                success: function (data) {
                    if (data.user) {
                        self.astroprintUser(data.user)
                        self.getDesigns(false);
                        self.getManufacturers();
                        self.unlinkedPrintFiles(false);
                    } else {
                        self.astroprintUser(false)
                    }
                    self.cam_status(data.connected)
                    self.can_print(data.can_print)
                    self.boxrouter_status(data.boxrouter_status)
                    if (!astroPrintPluginStarted) {
                        self.showAstroPrintPages()
                    }
                },
                error: function (data) {
                    console.error(data)
                    self.astroprintUser(false) //set false?
                    self.cam_status(false)
                    self.can_print(true) // set true?
                    if (!astroPrintPluginStarted) {
                        self.showAstroPrintPages()
                    }
                },
                dataType: "json"
            });
        }


        self.changeCameraStatus = function (data) {
            self.cam_status(data)
            new PNotify({
                title: gettext(data ? "Camera detected" : "Lost camera connection"),
                text: gettext(data ? "Your Octoprint camera is connected with AstroPrint" : "AstroPrint has lost connection with the camera"),
                type: data ? "success" : "error"
            });
        }

        self.authorizeAstroprint = function () {
            var ap_access_key = self.access_key()
            if (ap_access_key){
              var currentUrl = window.location.href.split('?')[0];
              currentUrl = window.location.href.split('#')[0];
              currentUrl = encodeURI(currentUrl);
              var url = astroprint_variables.appSite + "/authorize" +
                  "?client_id=" + astroprint_variables.appId +
                  "&redirect_uri=" + currentUrl +
                  "&scope=" + encodeURI("profile:read project:read design:read design:download print-file:read print-file:download print-job:read device:connect device:update device:read")+
                  "&state="+ap_access_key+
                  "&response_type=code";
              location.href = url;
            } else {
                new PNotify({
                    title: gettext("Missing Access Key"),
                    text: gettext("Access Key is missing, please provide a valid one"),
                    type: "error"
                });
            }
        }

        self.loginAstroprint = function (accessCode, apAccessKey) {
            var currentUrl = window.location.href.split('?')[0];
            $.ajax({
                type: "POST",
                contentType: "application/json; charset=utf-8",
                url: PLUGIN_BASEURL + "astroprint/login",
                data: JSON.stringify({
                  code: accessCode,
                  url: currentUrl,
                  ap_access_key: apAccessKey,
                  ap_box_id : astroprint_variables.boxId,
                  box_id : astroprint_variables.boxId
                }),
                dataType: "json",
                success: function (success) {
                    self.astroprintUser(success);
                    self.getDesigns(false);
                    self.unlinkedPrintFiles(false);
                    new PNotify({
                        title: gettext("AstroPrint Login successful"),
                        text: gettext("You are now logged to Astroprint as " + self.astroprintUser().email),
                        type: "success"
                    });
                },
                error: function (error) {
                    var title;
                    var text;
                    if (error.status && error.status == 403){
                        title = gettext("Login failed: Forbidden")
                        text = gettext(error.responseJSON.error_description)
                    } else if ( error.responseJSON.error ) {
                        title =  gettext("Login failed: " + error.responseJSON.error)
                        text = gettext(error.responseJSON.error_description)
                    } else {
                        title =  gettext("Login failed")
                        text = gettext("There was an error linking your Astroprint account, please try again later.")
                    }
                    new PNotify({
                        title: title,
                        text: text,
                        type: "error"
                    });
                }
            });
        }

        self.logOutAstroPrint = function () {
            self.logOut().then(function (success) {
                new PNotify({
                    title: gettext("AstroPrint Logout successful"),
                    text: gettext("You are now logged out of AstroPrint"),
                    type: "success"
                });
            }, function (error) {
                new PNotify({
                    title: gettext("AstroPrint Logout failed"),
                    text: gettext("There was an error logging out of AstroPrint."),
                    type: "error"
                });
            });
        };

        //Send from event (user allready has benn deleted from database)
        self.error401handling = function () {
            self.astroprintUser(false);
            new PNotify({
                title: gettext("AstroPrint session expired"),
                text: gettext("Your AstroPrint session has expired, please log again."),
                type: "error"
            });
        }

        //Only case we logout and we have to delete user, from client side
        self.logOut = function () {
            return new Promise(function (resolve, reject) {
                $.ajax({
                    type: "POST",
                    contentType: "application/json; charset=utf-8",
                    url: PLUGIN_BASEURL + "astroprint/logout",
                    dataType: "json",
                    success: function () {
                        self.astroprintUser(false);
                        resolve();
                    },
                    error: function () {
                        reject();
                    }
                });
            });
        }



        self.getDesigns = function (refresh = true) {
            self.designsRetrieved("loading");
            $.ajax({
                type: "GET",
                contentType: "application/json; charset=utf-8",
                url: PLUGIN_BASEURL + "astroprint/designs",
                start_time: new Date().getTime(),
                success: function (data) {
                    var designs = [];
                    for (var design of data.data) {
                        designs.push(
                            new Design(design.id, design.name, design.images.square, design.print_file_count, design.allow_download)
                        );
                    }
                    self.designList(designs);
                    var notify = function () {
                        new PNotify({
                            title: gettext("AstroPrint Designs Retrieved"),
                            text: gettext("Your designs and print files from AstroPrint have been refreshed"),
                            type: "success"
                        });
                    }
                    if ((new Date().getTime() - this.start_time) > 600) {
                        self.designsRetrieved("done");
                        if (refresh) {
                            notify();
                        }
                    } else {
                        setTimeout(function () {
                            self.designsRetrieved("done");
                            if (refresh) {
                                notify();
                            }
                        }, 600 - ((new Date().getTime() - this.start_time)));
                    }
                },
                error: function (data) {
                    if (data.status == 401) {
                        self.error401handling();
                    } else {
                        self.designsRetrieved("error");
                        new PNotify({
                            title: gettext("Error retrievind designs"),
                            text: gettext("There was an error retrieving AstroPrint desings, please try again later."),
                            type: "error"
                        });
                    }
                },
                dataType: "json"
            });
        };

        self.getPrintFiles = function (design) {
            if (design.printFilesCount()) {
                if (design.expanded()) {
                    design.expanded(false);
                } else {
                    if (!design.loadingPrintfiles()) {
                        if (design.printFiles().length == 0) {
                            design.loadingPrintfiles(true);
                            $.ajax({
                                type: "GET",
                                contentType: "application/json; charset=utf-8",
                                url: PLUGIN_BASEURL + "astroprint/printfiles",
                                data: {
                                    designId: design.id
                                },
                                start_time: new Date().getTime(),
                                success: function (data) {
                                    var printFiles = [];
                                    for (var p of data.data) {
                                        printFiles.push(
                                            new PrintFile(p.id, p.created, p.filename, design.image, p.info, p.format, p.printer, p.material, p.quality)
                                        );
                                    }
                                    design.printFilesCount(printFiles.length);
                                    design.printFiles(printFiles);
                                    design.loadingPrintfiles(false);
                                    design.expanded(true);
                                },
                                error: function (data) {
                                    if (data.status == 401) {
                                        self.error401handling();
                                    } else {
                                        design.loadingPrintfiles(false);
                                        new PNotify({
                                            title: gettext("Error retrieving Print Files"),
                                            text: gettext("There was an error retrieving print files, please try again later."),
                                            type: "error"
                                        });
                                    }
                                },
                                dataType: "json"
                            });
                        } else {
                            design.expanded(true);
                        }
                    }
                }
            }
        }

        self.unlinkedPrintFiles = function (refresh = true) {
            self.printFilesRetrieved("loading");
            $.ajax({
                type: "GET",
                contentType: "application/json; charset=utf-8",
                url: PLUGIN_BASEURL + "astroprint/printfiles",
                start_time: new Date().getTime(),
                success: function (data) {
                    var printFiles = [];
                    for (var p of data.data) {
                        printFiles.push(
                            new PrintFile(p.id, p.created, p.filename, null, p.info, p.format, p.printer, p.material, p.quality)
                        );
                    }
                    self.printFileList(printFiles);
                    var notify = function () {
                        new PNotify({
                            title: gettext("AstroPrint PrintFiles Retrieved"),
                            text: gettext("Your designs and print files from AstroPrint have been refreshed"),
                            type: "success"
                        });
                    }
                    if ((new Date().getTime() - this.start_time) > 600) {
                        self.printFilesRetrieved("done");
                        if (refresh) {
                            notify();
                        }
                    } else {
                        setTimeout(function () {
                            self.printFilesRetrieved("done");
                            if (refresh) {
                                notify();
                            }
                        }, 600 - ((new Date().getTime() - this.start_time)));
                    }
                },
                error: function (data) {
                    if (data.status == 401) {
                        self.error401handling();
                    } else {
                        self.designsRetrieved("error");
                        new PNotify({
                            title: gettext("Error retrievind printFiles"),
                            text: gettext("There was an error retrieving AstroPrint printFiles, please try again later."),
                            type: "error"
                        });
                    }
                },
                dataType: "json"
            });
        };


        self.expandPrintfile = function (printFile) {
            if (printFile.expanded()) {
                printFile.expanded(false);
            } else {
                printFile.expanded(true);
            }
        }

        self.downloadDesign = function (design) {
            if (self.isOctoprintAdmin()) {
                if (!self.downloadDialog().downloading() || self.downloadDialog().progress() == 100) {
                    var name = design.name
                    if (name.toLowerCase().substr(name.lastIndexOf('.') + 1, 3) != 'stl') {
                        name += '.stl';
                    }
                    design.downloading(true);
                    $.ajax({
                        type: "POST",
                        contentType: "application/json; charset=utf-8",
                        url: PLUGIN_BASEURL + "astroprint/downloadDesign",
                        data: JSON.stringify({ designId: design.id, name: name }),
                        dataType: "json",
                        success: function (data) {
                            self.downloadDialog().downloadStarted(design.id, design.name, design.image, design)
                        },
                        error: function (error) {
                            if (error.status == 401) {
                                self.error401handling();
                            } else {
                                design.downloading(false);
                                var text = "There was an error retrieving design, please try again later.";
                                var title = "Error retrieving Design";
                                if (error.status == 400) {
                                    title = ("Error adding Design");
                                    text = error.responseText;
                                }
                                new PNotify({
                                    title: gettext(title),
                                    text: gettext(text),
                                    type: "error"
                                });
                            }
                        }
                    });
                }
            } else {
                new PNotify({
                    title: gettext("Please log in"),
                    text: gettext("You must be logged onto your OctoPrint Account to be able to download designs."),
                    type: "info"
                });
            }
        }

        self.printPrintFile = function (printFile)
        {
            self.downloadPrintFile(printFile, true)
        }

        self.downloadPrintFile = function (printFile, printNow = false) {
            printNow = printNow !== true ? false : true
            if (self.isOctoprintAdmin()) {
                if (!self.downloadDialog().downloading() || self.downloadDialog().progress() == 100) {
                    printFile.downloading(true);
                    $.ajax({
                        type: "POST",
                        contentType: "application/json; charset=utf-8",
                        url: PLUGIN_BASEURL + "astroprint/downloadPrintFile",
                        data: JSON.stringify({ printFileId: printFile.id, name: printFile.filename, printNow : printNow }),
                        dataType: "text",
                        success: function (data) {
                            data = JSON.parse(data)
                            if (data['state'] == "downloading") {
                                self.downloadDialog().downloadStarted(printFile.id, printFile.filename, printFile.image, printFile);
                            } else {
                                self.downloadDialog().downloadStarted(printFile.id, printFile.filename, printFile.image, printFile);
                                self.downloadDialog().uploadProgress(printFile.id, 100);
                            }
                        },
                        error: function (error) {
                            if (error.status == 401) {
                                self.error401handling();
                            } else {
                                printFile.downloading(false);
                                var text = "There was an error retrieving print file, please try again later.";
                                var title = "Error retrieving Design";
                                if (error.status == 400) {
                                    title = ("Error adding Design");
                                    text = error.responseText;
                                }
                                new PNotify({
                                    title: gettext(title),
                                    text: gettext(text),
                                    type: "error"
                                });
                            }

                        }
                    });
                }
            } else {
                new PNotify({
                    title: gettext("Please log in"),
                    text: gettext("You must be logged on your OctoPrint Account to be able to download print files."),
                    type: "info"
                });
            }
        }

        self.scanForCamera = function () {
            if (!self.cam_status()) {//loading could be confused when camera is active
                self.cam_status('loading');
            }
            $.ajax({
                type: "GET",
                contentType: "application/json; charset=utf-8",
                start_time: new Date().getTime(),
                url: PLUGIN_BASEURL + "astroprint/checkcamerastatus",
                start_time: new Date().getTime(),
                success: function (data) {
                    if ((new Date().getTime() - this.start_time) > 800) { //give some time to make the user sure that it really looked for cam
                        self.cam_status(data.connected)
                    } else {
                        setTimeout(function () {
                            self.cam_status(data.connected)
                        }, 800 - ((new Date().getTime() - this.start_time)));
                    }
                },
                error: function (data) {
                    self.cam_status(false)//set false?
                },
                dataType: "json"
            });
        };

        //handle asyncronous login state from octoprint
        self.checkIsLoggedOnConnect = function () {
            setTimeout(function () {
                self.isOctoprintAdmin(self.loginState.isAdmin())
                if (self.isOctoprintAdmin()) {
                    self.initialice_variables();
                } else {
                    self.showAstroPrintPages();
                }
            }, 100);
        };

        self.checkApiOption = function () {
            $('#navbar_show_settings').trigger( "click" );
            $('#settingsTabs a[href="#settings_plugin_astroprint"]').tab('show')
            setTimeout( ()=>{
                document.getElementById('goToastrocors').click();
            }, 200)
        }

        self.showAstroPrintPages = function () {
            $("#startingUpPlugin").hide()
            $("#noOctoprintLogged").show();
            $("#noAstroprintLogged").show();
            $("#astroPrintLogged").show();
            astroPrintPluginStarted = true;
        }

        self.goToAstroPrintTab = function () {
            $('#tab_plugin_astroprint_link a').trigger( "click" );
            $('.close','#settings_dialog').trigger( "click" );
        }

        //log with the code
        self._getUrlParameter = function (sParam) {
            var sPageURL = decodeURIComponent(window.location.search.substring(1)),
                sURLVariables = sPageURL.split('&'),
                sParameterName,
                i;

            for (var i = 0; i < sURLVariables.length; i++) {
                sParameterName = sURLVariables[i].split('=');
                if (sParameterName[0] === sParam) {
                    return sParameterName[1] === undefined ? true : sParameterName[1];
                }
            }
        };

        //Log in before startupComplete saves some time
        var code = self._getUrlParameter("code");
        var state = self._getUrlParameter("state");
        if (code && state) {
            self.loginAstroprint(code, state);
            window.history.replaceState({}, document.title, "/");
        }

        self.onStartupComplete = function () {
            setTimeout(self.checkIsLoggedOnConnect(), 1000);
        }

        self.moveToApi = function (){
            $('#settingsTabs a[href="#settings_api"]').tab('show')
            $('#settings-apiCors').closest("label").animate({fontSize : "18px"}, 1000 ).animate({fontSize : "15px"}, 1000 )
        }

        //change boxName

        self.changingname = ko.observable(false)
        self.changeNameDialog = $("#changeBoxName");
        self.changeNameDialog.on("shown", function() {
            $("input", self.changeNameDialog).focus();
        });


        self.changeNameDialog.on('hidden', function () {
            $("#changeBoxName .control-group").removeClass("error")
            $("#changeBoxName .help-inline").addClass("hide")
            self.cacheBoxName(self.boxName());
        })

        self.changeName = function (){
            $("#changeBoxName .control-group").removeClass("error")
            $("#changeBoxName .help-inline").addClass("hide")
            hostname = /^[A-Za-z0-9\-]+$/
            if (hostname.test(self.cacheBoxName())){
                self.changingname(true)
                $.ajax({
                    type: "POST",
                    contentType: "application/json; charset=utf-8",
                    url: PLUGIN_BASEURL + "astroprint/changename",
                    data: JSON.stringify({ 'name': self.cacheBoxName() }),
                    dataType: "json",
                    success: function () {
                        self.boxName(self.cacheBoxName());
                        self.changingname(false)
                        $('#changeBoxName').modal('hide');
                    },
                    error: function (error) {
                        self.changingname(false)
                        console.error(error)
                    }
                });
            } else {
                $("#changeBoxName .control-group").addClass("error")
                $("#changeBoxName .help-inline").removeClass("hide")
            }
        }



    }

    // view model class, parameters for constructor, container to bind to
    OCTOPRINT_VIEWMODELS.push([
        AstroprintViewModel,
        ["settingsViewModel", "loginStateViewModel"],
        ["#settings_plugin_astroprint", "#tab_plugin_astroprint"]
    ]);
});
