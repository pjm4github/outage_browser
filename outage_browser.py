# -*- coding: utf-8 -*-

"""
Module implementing MainWindow.
"""

from PyQt4.QtCore import pyqtSignature, QStringList, QString, QDate, QTime, Qt, SIGNAL, SLOT
from PyQt4.QtGui import QApplication, QMainWindow, QAbstractItemView, QPalette, QColor, QLabel, QMessageBox

from PyQt4 import QtGui

from Ui_outage_browser import Ui_MainWindow
from lat_lon_distance import lat_lon_distance
from make_kml_onts_function import make_kml, make_kml_ont_eligibilities, make_kml_utility_assets, make_kml_outage_marker
import g_config
import g_eon_api_bridge
import json
import arrow
import logging
import logging.handlers
import os
import datetime
import csv
import re
from math import floor, ceil
import subprocess

unique_str = datetime.datetime.now().isoformat().replace(':', '_').replace('.', '_').replace('-', '_')
LOG_FILENAME = '.' + os.sep + 'log/ob_'+unique_str+'.log'
handler = logging.handlers.RotatingFileHandler(LOG_FILENAME, maxBytes=5000000, backupCount=50)
handler.setFormatter(logging.Formatter(g_config.LOG_FORMAT, datefmt='%m-%d %H:%M:%S'))
handler.setLevel(logging.DEBUG)
# Add this handler to the root logger
logging.getLogger('').addHandler(handler)


class MainWindow(QMainWindow, Ui_MainWindow):
    """
    Class documentation goes here.
    """
    def __init__(self, parent=None, app=None):
        """
        Constructor
        @param parent reference to the parent widget (QWidget)
        """
        QMainWindow.__init__(self, parent)
        self.setupUi(self)
        self.status_label = QLabel()
        self.browser_status_bar.addPermanentWidget(self.status_label)
        # Add the log message handler to the logger

        self.working_radius = 0.12  # This will hold the radius
        self.eon_api_bridge = g_eon_api_bridge.EonApiBridge()
        self.asset_table_array = [[]]
        self.page_size = 50
        self.app = app
        self.abort = False
        self.known_onts = {}  # This will be a dictionary of known ONTs that can be selected
        self.ONT_COLUMN = 6  # The column of the asset table that contains the ONT array string
        self.global_settings = {'DEFAULT_SAVE_LOCATION': './',
                                'DEFAULT_FILE_NAME': 'RAW_ALARMS',
                                'DEFAULT_KML_FILE': 'groomer_browser'}
        self.operation_progress_bar.setValue(0)
        self.operation_progress_bar.setFixedHeight(10)
        self.alarm_files = set()
        self.source_base = r'C:' + os.sep + r'repo' + os.sep + r'Aptect' + \
                           os.sep + r'Verizon' + os.sep + r'Workproduct' + \
                           os.sep + r'EON-IOT' + os.sep + r'Replayer'
        self.source_dir = r''
        self.alarms_dir = r''
        self.start_time = {'month': '05', 'day': '01', 'year': '15', 'hour': '06', 'minute': '45', }
        self.end_time = {'month': '05', 'day': '31', 'year': '15', 'hour': '23', 'minute': '45', }
        self.start_time_dirty = False
        self.end_time_dirty = False
        self.on_start_date_time_edit_editingFinished()
        self.on_end_date_time_edit_editingFinished()
        self.collect_alarm_file_set()
        self.export_directory = r''
        self.raw_event_collection = {}  # An empty dictionary that will hold all the ONT items
        # Add a clipboard
        self.clip = QApplication.clipboard()
        self.ont_table_widget.setContextMenuPolicy(Qt.ActionsContextMenu)
        self.ont_table_widget.contextMenuEvent = self.contextMenuEvent
        #self.connect(self.ont_table_widget,
        #             SIGNAL("customContextMenuRequested(QPoint)"),
        #             self,
        #             SLOT("on_ont_table_widget_customContextMenuRequested(QPoint)"))

        # See http://pyqt.sourceforge.net/Docs/PyQt4/qt.html
        #self.ont_table_widget.customContextMenuRequested()

        #.customContextMenuRequested.

        #    .connect(self.on_ont_table_widget_customContextMenuRequested)

    def contextMenuEvent(self, event):
        self.menu = QtGui.QMenu(self)
        copy_action = QtGui.QAction('Copy', self)
        copy_action.triggered.connect(self.copy_table)
        self.menu.addAction(copy_action)
        # add other required actions
        self.menu.popup(QtGui.QCursor.pos())


    def load_utility_asset_table(self):
        this_data = self.asset_table_array
        row_count = 0
        for row in this_data:
            if row_count == 0:
                q_string_list = QStringList()
                for header_item in row:
                    q_string_list.append(header_item.strip())
                # console_write("header = '%s'" % score_header)
                self.assets_table_widget.setRowCount(0)
                self.assets_table_widget.setColumnCount(len(row))
                # tool_table_widget = QtGui.QTableWidget(10, len(score_header))
                self.assets_table_widget.setHorizontalHeaderLabels(q_string_list)
                self.assets_table_widget.verticalHeader().setVisible(True)
                # self.assets_table_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
                # self.assets_table_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
                self.assets_table_widget.setShowGrid(True)
                self.assets_table_widget.setSelectionBehavior(QAbstractItemView.SelectItems)
                row_count = 1
            else:
                current_row = self.assets_table_widget.rowCount()
                self.assets_table_widget.insertRow(current_row)
                for col, this_item in enumerate(row):
                    item = QtGui.QTableWidgetItem(QString(this_item.strip()))
                    self.assets_table_widget.setItem(current_row, col, item)

        if self.app is not None:
            self.app.processEvents()
        if self.enable_asset_sort.isChecked():
            self.assets_table_widget.setSortingEnabled(True)
        else:
            self.assets_table_widget.setSortingEnabled(False)

        self.assets_table_widget.resizeColumnsToContents()

    @pyqtSignature("")
    def on_parse_job_data_clicked(self):
        """
        Slot documentation goes here.
        Contents of the feeder test outage is
        JOBNUMBER	NUM_INTER	TIMERECEIVED	TIMECOMPLETED	WINDOW	ADDRESS	MUNICIPALITY	FEEDERNUMBER	LATITUDE	LONGITUDE	DISTANCE	UNITS	PLATE	NOTES

        Each separated by a tab

        """
        self.browser_status_bar.showMessage("Parsing the job data")
        self.alarm_load_label.setText(QString(''))
        self.page_load_label.setText(QString(''))
        self.ont_area_load_label.setText(QString(''))
        job_data_array = str(self.job_data_line_edit.text()).split('\t')
        if len(job_data_array) < 12:
            qp = QPalette()
            qp.setColor(QPalette.Base, QColor(255, 120, 120))
            self.job_data_line_edit.setPalette(qp)
        else:
            qp = QPalette()
            qp.setColor(QPalette.Base, QColor(255, 255, 255))
            self.job_data_line_edit.setPalette(qp)
            parsed_dict = {'JOB_NUMBER': job_data_array[0],
                           'NUM_INTER': job_data_array[1],
                           'TIME_RECEIVED': job_data_array[2],
                           'TIME_COMPLETED': job_data_array[3],
                           'WINDOW': job_data_array[4],
                           'ADDRESS': job_data_array[5],
                           'MUNICIPALITY': job_data_array[6],
                           'FEEDER_NUMBER': job_data_array[7],
                           'LATITUDE': job_data_array[8],
                           'LONGITUDE': job_data_array[9],
                           'DISTANCE': job_data_array[10],
                           'UNITS': job_data_array[11]}

            self.job_number_line_edit.setText(parsed_dict['JOB_NUMBER'])
            self.export_directory = parsed_dict['JOB_NUMBER']
            self.num_customer_line_edit.setText(parsed_dict['NUM_INTER'])
            self.time_received_line_edit.setText(parsed_dict['TIME_RECEIVED'])
            self.time_complete_line_edit.setText(parsed_dict['TIME_COMPLETED'])

            time_received = parsed_dict['TIME_RECEIVED'].split()
            the_date = time_received[0].split('/')
            year = int(the_date[2])
            month = int(the_date[0])
            day = int(the_date[1])
            the_start_date = QDate(year, month, day)
            the_time = time_received[1].split(':')
            hour = int(the_time[0])
            minute = int(floor(float(the_time[1])/ 60.0 * 4.0) * 15)
            the_start_time = QTime(hour, minute, 0, 0)
            self.start_date_time_edit.setDate(the_start_date.addDays(-1))  # , the_start_time)
            self.start_date_time_edit.setTime(the_start_time)

            self.on_start_date_time_edit_editingFinished()

            time_completed = parsed_dict['TIME_COMPLETED'].split()
            the_date = time_completed[0].split('/')
            year = int(the_date[2])
            month = int(the_date[0])
            day = int(the_date[1])
            the_end_date = QDate(year, month, day)
            the_time = time_completed[1].split(':')
            hour = int(the_time[0])
            minute = int(floor(float(the_time[1])/ 60.0 * 4.0) * 15)

            the_end_time = QTime(hour, minute, 0, 0)
            self.end_date_time_edit.setDate(the_end_date.addDays(1))  # , the_end_time)
            self.end_date_time_edit.setTime(the_end_time)
            self.on_end_date_time_edit_editingFinished()

            self.address_line_edit.setText(parsed_dict['ADDRESS'])
            self.time_span_window.setText(parsed_dict['WINDOW'])

            self.city_state_line_edit.setText(parsed_dict['ADDRESS'])
            feeder_name = parsed_dict['FEEDER_NUMBER']
            this_index = self.feeder_combo_box.findText(feeder_name)
            if this_index < 0:
                this_index = self.feeder_combo_box.findText(feeder_name[1:])
            if this_index < 0:
                this_index = self.feeder_combo_box.findText(feeder_name[1:-1])
            if this_index < 0:
                this_index = self.feeder_combo_box.findText(feeder_name[0:-1])
            if this_index < 0:
                # This is an error condition so flag the user
                qp = QPalette()
                qp.setColor(QPalette.Base, QColor(255, 120, 120))
                self.feeder_combo_box.setPalette(qp)
            else:
                qp = QPalette()
                qp.setColor(QPalette.Base, QColor(255, 255, 255))
                self.feeder_combo_box.setPalette(qp)
                self.feeder_combo_box.setCurrentIndex(this_index)
            self.lat_lon_line_edit.setText(parsed_dict['LATITUDE'] + ', ' + parsed_dict['LONGITUDE'])

            # Also load the ont item list
            self.ont_lat_lon_line_edit.setText(parsed_dict['LATITUDE'] + ', ' + parsed_dict['LONGITUDE'])
            self.ont_radius_line_edit.setText(parsed_dict['DISTANCE'])
            # Clear all the default values
            self.asset_table_array = [[]]
            self.known_onts = {}
            self.on_clear_collection_pushbutton_clicked()
            self.clear_utility_asset_table()
            self.clear_ont_table_widget()
            self.clear_alarm_table()
            feeder = str(self.feeder_combo_box.currentText())
            filename = parsed_dict['ADDRESS'].replace(' ', '_') + '(' + feeder + ')' + '_ALARMS.csv'
            self.export_directory_line_edit.setText(filename)

    @pyqtSignature("")
    def on_get_utility_assets_by_feeder_clicked(self):
        """
        Slot documentation goes here.
        """
        # call this API http://10.123.0.27:8080/eon360/api/utilities/circuits/SPROUT?p=3&s=200
        this_circuit_id = str(self.feeder_combo_box.currentText())

        self.browser_status_bar.showMessage("Get utility data assets for feeder = %s" % this_circuit_id)
        page_num = 0
        self.page_load_label.setText('Loading pg 1, please wait...')
        if self.app is not None:
            self.app.processEvents()
        more_pages = False
        self.browser_status_bar.showMessage(
            ("Calling API [utilities_get_utilities_circuits_circuit_id]  CIRCUIT_ID = %s " %
             this_circuit_id)
        )
        self.abort = False
        dd = self.eon_api_bridge.utilities_get_utilities_circuits_circuit_id(circuit_id=this_circuit_id,
                                                                             company="CEDRAFT",
                                                                             p=page_num, s=self.page_size)

        timeout_reset_value = self.eon_api_bridge.base_timeout
        while not dd and self.eon_api_bridge.status == "Timeout" and self.eon_api_bridge.base_timeout < 360:
            self.eon_api_bridge.base_timeout *= 2
            self.browser_status_bar.showMessage("doubling timeout value to %d sec" % self.eon_api_bridge.base_timeout)
            dd = self.eon_api_bridge.utilities_get_utilities_circuits_circuit_id(circuit_id=this_circuit_id,
                                                                                 company="CEDRAFT",
                                                                                 p=page_num, s=self.page_size)
        j = 1
        self.eon_api_bridge.base_timeout = timeout_reset_value
        if dd:
            if 'status_code' in dd.keys():
                if dd['status_code'] == 500:
                    self.browser_status_bar.showMessage(
                        ("API TIMEOUT [utilities_get_utilities_circuits_circuit_id]  CIRCUIT_ID = %s " % this_circuit_id))
                    self.abort = True
        if dd and not self.abort:
            self.clear_utility_asset_table()
            self.browser_status_bar.showMessage('Number of items in page is %d' % dd['pageTotalItems'])
            self.asset_table_array = [[]]
            self.asset_table_array[0].append('Asset ID')
            self.asset_table_array[0].append('#')
            self.asset_table_array[0].append('Address')
            self.asset_table_array[0].append('Latitude')
            self.asset_table_array[0].append('Longitude')
            self.asset_table_array[0].append('CE Map')
            self.asset_table_array[0].append('ONTs')
            self.ONT_COLUMN = 6
            for this_item in dd['eonUtilityEntries']:
                self.asset_table_array.append([])
                asset_id = this_item['transformerID']
                self.asset_table_array[j].append(asset_id)
                sa = json.loads(this_item['serviceAddress'])
                if sa['Address']:
                    service_address = sa['Address'].split()
                    self.asset_table_array[j].append(service_address[0])  # house number
                    self.asset_table_array[j].append(r' '.join(service_address[1:]))  # rest of the street
                else:
                    self.asset_table_array[j].append('')  # house number
                    self.asset_table_array[j].append('')  # rest of the street
                latitude = this_item['latitude']
                self.asset_table_array[j].append('%f' % latitude)
                longitude = this_item['longitude']
                self.asset_table_array[j].append('%f' % longitude)
                cemap = sa['CE Map ID']
                self.asset_table_array[j].append(cemap)
                eligibility_list = this_item['eligibilityList']
                ont_array_str = ''
                for this_ont in eligibility_list:
                    if this_ont['ontSerialNumber'] not in self.known_onts.keys():
                        self.known_onts[this_ont['ontSerialNumber']] = \
                            {'ontAddress': this_ont['ontAddress'],
                             'latitude': this_ont['latitude'],
                             'longitude': this_ont['longitude'],
                             'linked_assets': [this_item['transformerID']]}
                    else:
                        self.known_onts[this_ont['ontSerialNumber']]['linked_assets'].append(this_item['transformerID'])
                        # linked_assets = list(self.known_onts[this_ont['ontSerialNumber']]['linked_assets'])
                        # linked_assets.append([this_ont['ontSerialNumber']])
                        # self.known_onts[this_ont['ontSerialNumber']] = \
                        #    {'ontAddress': this_ont['ontAddress'],
                        #     'latitude': this_ont['latitude'],
                        #     'longitude': this_ont['longitude'],
                        #     'linked_assets': linked_assets }
                    ont_array_str += ('%s|' % this_ont['ontSerialNumber'])
                self.asset_table_array[j].append(ont_array_str)
                j += 1

            self.load_utility_asset_table()

            if dd['pageTotalItems'] < self.page_size:
                more_pages = False
            else:
                more_pages = True
        # Loop here until no more utility components of the first collection are found

        while more_pages and dd is not None and not self.abort:
            page_num += 1
            self.page_load_label.setText('Loading pg %d of %d' % ((page_num + 1), (dd['totalPages'])))
            self.operation_progress_bar.setValue(((page_num + 1)*100)/(dd['totalPages']))
            if self.app is not None:
                self.app.processEvents()
            # self.repaint()
            self.browser_status_bar.showMessage("Calling API [utilities_get_utilities_circuits_circuit_id]")
            dd = self.eon_api_bridge.utilities_get_utilities_circuits_circuit_id(circuit_id=this_circuit_id,
                                                                                 company="CEDRAFT",
                                                                                 p=page_num, s=self.page_size)

            timeout_reset_value = self.eon_api_bridge.base_timeout
            while not dd and self.eon_api_bridge.status == "Timeout" and self.eon_api_bridge.base_timeout < 360:
                self.eon_api_bridge.base_timeout *= 2
                self.browser_status_bar.showMessage(
                    "doubling timeout value to %d sec" % self.eon_api_bridge.base_timeout)
                dd = self.eon_api_bridge.utilities_get_utilities_circuits_circuit_id(circuit_id=this_circuit_id,
                                                                                     company="CEDRAFT",
                                                                                     p=page_num, s=self.page_size)
            if not dd:
                self.browser_status_bar.showMessage(
                    ("Giving up because base timeout exceeded [utilities_get_utilities_circuits_circuit_id]  "
                     "CIRCUIT_ID = %s " % this_circuit_id))
                self.abort = True
                self.eon_api_bridge.base_timeout = timeout_reset_value
            else:
                self.eon_api_bridge.base_timeout = timeout_reset_value
                if 'status_code' in dd.keys():
                    if dd['status_code'] == 500:
                        self.browser_status_bar.showMessage(
                            ("API TIMEOUT [utilities_get_utilities_circuits_circuit_id]  CIRCUIT_ID = %s " % this_circuit_id))
                        self.abort = True
            if dd:
                self.browser_status_bar.showMessage('Number of items in page is %d' % dd['pageTotalItems'])
                for this_item in dd['eonUtilityEntries']:
                    self.asset_table_array.append([])
                    asset_id = this_item['transformerID']
                    self.asset_table_array[j].append(asset_id)
                    sa = json.loads(this_item['serviceAddress'])
                    if sa['Address']:
                        service_address = sa['Address'].split()
                        self.asset_table_array[j].append(service_address[0])  # house number
                        self.asset_table_array[j].append(r' '.join(service_address[1:]))  # rest of the street
                    else:
                        self.asset_table_array[j].append('')  # house number
                        self.asset_table_array[j].append('')  # rest of the street
                    latitude = this_item['latitude']
                    self.asset_table_array[j].append('%f' % latitude)
                    longitude = this_item['longitude']
                    self.asset_table_array[j].append('%f' % longitude)
                    cemap = sa['CE Map ID']
                    self.asset_table_array[j].append(cemap)
                    eligibility_list = this_item['eligibilityList']
                    ont_array_str = ''
                    for this_ont in eligibility_list:
                        if this_ont['ontSerialNumber'] not in self.known_onts.keys():
                            self.known_onts[this_ont['ontSerialNumber']] = \
                                {'ontAddress': this_ont['ontAddress'],
                                 'latitude': this_ont['latitude'],
                                 'longitude': this_ont['longitude'],
                                 'linked_assets': [this_item['transformerID']]}
                        else:
                            # linked_assets = list(self.known_onts[this_ont['ontSerialNumber']]['linked_assets'])
                            # linked_assets.append([this_ont['ontSerialNumber']])
                            self.known_onts[this_ont['ontSerialNumber']]['linked_assets'].append(
                                this_item['transformerID'])
                            # self.known_onts[this_ont['ontSerialNumber']] = \
                            #    {'ontAddress': this_ont['ontAddress'],
                            #     'latitude': this_ont['latitude'],
                            #     'longitude': this_ont['longitude'],
                            #     'linked_assets': set(linked_assets) }

                        ont_array_str += ('%s|' % this_ont['ontSerialNumber'])
                    self.asset_table_array[j].append(ont_array_str)
                    j += 1
                self.load_utility_asset_table()

                if dd['pageTotalItems'] < self.page_size:
                    more_pages = False
        if self.abort:
            self.show_cancel()
            self.page_load_label.setText('Abort: Loaded %d pages.' % (page_num + 1))
        else:
            self.page_load_label.setText('Done: Loaded %d pages.' % (page_num + 1))
        self.operation_progress_bar.setValue(0)
        self.abort = False

    @pyqtSignature("")
    def on_get_onts_in_area_clicked(self):
        """
        Slot documentation goes here.
        """
        self.browser_status_bar.showMessage("Getting onts in the area specified.")
        self.clear_ont_table_widget()
        self.ont_area_load_label.setText('Loading pg 1...')
        if self.app:
            self.app.processEvents()
        more_pages = False
        lat_lon = str(self.ont_lat_lon_line_edit.text()).split()
        if len(lat_lon) < 2:
            lat_lon = str(self.ont_lat_lon_line_edit.text()).split(',')
        if len(lat_lon) == 2:
            qp = QPalette()
            qp.setColor(QPalette.Base, QColor(255, 255, 255))
            self.ont_lat_lon_line_edit.setPalette(qp)
            self.browser_status_bar.showMessage("Calling API [query_post_query]")
            page_num = 0
            self.ont_area_load_label.setText('Loading pg %d' % (page_num + 1))
            self.operation_progress_bar.setValue(((page_num + 1)*100)/50)
            latitude = float(lat_lon[0].replace(',', ''))
            longitude = float(lat_lon[1])
            radius = float(self.ont_radius_line_edit.text())
            query_parameter = json.dumps({"itemType": "ELIGIBILITY",
                                          "circle": {
                                              "latitude": latitude,
                                              "longitude": longitude,
                                              "radius": radius,
                                              "unit": "MILES"},
                                          "pageParameter": {
                                              "page": page_num,
                                              "size": self.page_size}})
            dd = self.eon_api_bridge.query_post_query(query_parameter=query_parameter)
            timeout_reset_value = self.eon_api_bridge.base_timeout
            while not dd and self.eon_api_bridge.status == "Timeout" and self.eon_api_bridge.base_timeout < 360:
                self.eon_api_bridge.base_timeout *= 2
                self.browser_status_bar.showMessage(
                    "doubling timeout value to %d sec" % self.eon_api_bridge.base_timeout)
                dd = self.eon_api_bridge.query_post_query(query_parameter=query_parameter)
            self.eon_api_bridge.base_timeout = timeout_reset_value
            if dd:
                self.browser_status_bar.showMessage("Got a result")
                self.browser_status_bar.showMessage(
                    'Number of items in page is %d' % dd['eligibility']['pageTotalItems'])
                if dd['eligibility']['pageTotalItems'] < self.page_size:
                    more_pages = False
                else:
                    more_pages = True
                onts = dd['eligibility']['dataItems']
                ont_array = []
                for this_ont in onts:
                    # {u'alarmID': u'PKSKNYPSOL2*LET-3*10*1*19',
                    #  u'company': u'',
                    #  u'createdAtTimestamp': 1419773212131L,
                    #  u'errorCode': u'0.89',
                    #  u'guid': u'39b2861d-35aa-4194-a71b-71cbdb8133ee',
                    #  u'id': u'54a0051ce4b040db6354cc0c',
                    #  u'lastModifiedAtTimestamp': 1419773212131L,
                    #  u'latitude': 41.309731,
                    #  u'longitude': -73.914932,
                    #  u'modelCoefficients': None,
                    #  u'ontAddress': u'26 Brook Pl,Cortlandt Manor,NY,10567',
                    #  u'ontSerialNumber': u'56480448',
                    #  u'version': 0}
                    # row=['ONT','#', 'Address','Latitude','Longitude', 'Distance']
                    street_address = this_ont['ontAddress'].split()
                    ont_line = [this_ont['ontSerialNumber'],
                                street_address[0],
                                r' '.join(street_address[1:]),
                                '%f' % this_ont['latitude'],
                                '%f' % this_ont['longitude'],
                                '%f' % lat_lon_distance(latitude, longitude, this_ont['latitude'],
                                                        this_ont['longitude'])
                                ]
                    ont_array.append(ont_line)
                    if this_ont['ontSerialNumber'] not in self.known_onts.keys():
                        self.known_onts[this_ont['ontSerialNumber']] = \
                            {'ontAddress': this_ont['ontAddress'],
                             'latitude': this_ont['latitude'],
                             'longitude': this_ont['longitude'],
                             'linked_assets': []}
                        # Blank out the ONT raw event collection
                        self.raw_event_collection[this_ont['ontSerialNumber']] = []
                row = ['ONT', '#', 'Address', 'Latitude', 'Longitude', 'Distance']
                q_string_list = QStringList()
                for header_item in row:
                    q_string_list.append(header_item.strip())
                # console_write("header = '%s'" % score_header)
                self.ont_table_widget.setRowCount(0)
                self.ont_table_widget.setColumnCount(len(row))
                # tool_table_widget = QtGui.QTableWidget(10, len(score_header))
                self.ont_table_widget.setHorizontalHeaderLabels(q_string_list)
                self.ont_table_widget.verticalHeader().setVisible(True)
                # self.ont_table_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
                # self.ont_table_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
                self.ont_table_widget.setShowGrid(True)
                self.ont_table_widget.setSelectionBehavior(QAbstractItemView.SelectItems)

                for this_ont in ont_array:
                    row = this_ont
                    current_row = self.ont_table_widget.rowCount()
                    self.ont_table_widget.insertRow(current_row)
                    for col, this_item in enumerate(row):
                        item = QtGui.QTableWidgetItem(QString(this_item.strip()))
                        self.ont_table_widget.setItem(current_row, col, item)

            # Loop here until no more utility components of the first collection are found
            while more_pages and dd is not None and not self.abort:
                page_num += 1
                # self.page_load_label.setText('Loading page %d of %d' % (page_num, (dd['totalPages']-1)))
                if self.app is not None:
                    self.app.processEvents()
                self.browser_status_bar.showMessage("Calling API [query_post_query]")
                self.ont_area_load_label.setText('Loading pg %d' % (page_num + 1))
                if self.app:
                    self.app.processEvents()
                query_parameter = json.dumps({
                    "itemType": "ELIGIBILITY",
                    "circle": {
                        "latitude": latitude,
                        "longitude": longitude,
                        "radius": radius,
                        "unit": "MILES"},
                    "pageParameter": {
                        "page": page_num,
                        "size": self.page_size}})
                dd = self.eon_api_bridge.query_post_query(query_parameter=query_parameter)
                timeout_reset_value = self.eon_api_bridge.base_timeout
                while not dd and self.eon_api_bridge.status == "Timeout" and self.eon_api_bridge.base_timeout < 360:
                    self.eon_api_bridge.base_timeout *= 2
                    self.browser_status_bar.showMessage(
                        "doubling timeout value to %d sec" % self.eon_api_bridge.base_timeout)
                    dd = self.eon_api_bridge.query_post_query(query_parameter=query_parameter)
                self.eon_api_bridge.base_timeout = timeout_reset_value
                if dd:
                    self.browser_status_bar.showMessage("Got a result")
                    self.browser_status_bar.showMessage(
                        'Number of items in page is %d' % dd['eligibility']['pageTotalItems'])
                    if dd['eligibility']['pageTotalItems'] < self.page_size:
                        more_pages = False
                    else:
                        more_pages = True
                    onts = dd['eligibility']['dataItems']
                    ont_array = []
                    for this_ont in onts:
                        # {u'alarmID': u'PKSKNYPSOL2*LET-3*10*1*19',
                        #  u'company': u'',
                        #  u'createdAtTimestamp': 1419773212131L,
                        #  u'errorCode': u'0.89',
                        #  u'guid': u'39b2861d-35aa-4194-a71b-71cbdb8133ee',
                        #  u'id': u'54a0051ce4b040db6354cc0c',
                        #  u'lastModifiedAtTimestamp': 1419773212131L,
                        #  u'latitude': 41.309731,
                        #  u'longitude': -73.914932,
                        #  u'modelCoefficients': None,
                        #  u'ontAddress': u'26 Brook Pl,Cortlandt Manor,NY,10567',
                        #  u'ontSerialNumber': u'56480448',
                        #  u'version': 0}
                        # row=['ONT','#', 'Address','Latitude','Longitude']
                        street_address = this_ont['ontAddress'].split()
                        ont_line = [this_ont['ontSerialNumber'],
                                    street_address[0],
                                    r' '.join(street_address[1:]),
                                    '%f' % this_ont['latitude'],
                                    '%f' % this_ont['longitude'],
                                    '%f' % lat_lon_distance(latitude, longitude, this_ont['latitude'],
                                                            this_ont['longitude'])
                                    ]
                        ont_array.append(ont_line)
                        if this_ont['ontSerialNumber'] not in self.known_onts.keys():
                            self.known_onts[this_ont['ontSerialNumber']] = \
                                {'ontAddress': this_ont['ontAddress'],
                                 'latitude': this_ont['latitude'],
                                 'longitude': this_ont['longitude'],
                                 'linked_assets': []}
                            self.raw_event_collection[this_ont['ontSerialNumber']] = []
                    for this_ont in ont_array:
                        row = this_ont
                        current_row = self.ont_table_widget.rowCount()
                        self.ont_table_widget.insertRow(current_row)
                        for col, this_item in enumerate(row):
                            item = QtGui.QTableWidgetItem(QString(this_item.strip()))
                            self.ont_table_widget.setItem(current_row, col, item)
            if self.abort:
                self.show_cancel()
                self.ont_area_load_label.setText('Abort: Loaded %d pages.' % (page_num + 1))
            else:
                self.ont_area_load_label.setText('Done: Loaded %d pages.' % (page_num + 1))
            self.operation_progress_bar.setValue(0)
            self.abort = False
            self.ont_table_widget.resizeColumnsToContents()
            if self.enable_ont_sort.isChecked():
                self.ont_table_widget.setSortingEnabled(True)
            else:
                self.ont_table_widget.setSortingEnabled(False)
        else:
            self.browser_status_bar.showMessage("There must be 2 values in the lat/lon box")
            qp = QPalette()
            qp.setColor(QPalette.Base, QColor(255, 120, 120))
            self.ont_lat_lon_line_edit.setPalette(qp)
            self.ont_area_load_label.setText('[]')

    @pyqtSignature("")
    def on_get_raw_alarms_4_onts_clicked(self):
        """
        Slot documentation goes here.
        """
        self.clear_alarm_table()
        ont_items = self.ont_collection_table_widget.selectedItems()
        ont_collection = set()
        rows_collection = set()
        if ont_items:
            for idx in self.ont_collection_table_widget.selectedIndexes():
                rows_collection.add(idx.row())
            for this_row in rows_collection:
                ont = str(self.ont_collection_table_widget.item(this_row, 0).text())
                ont_collection.add(ont)
        #####
        # Make a call to get the alarms for this ONT then populate the table
        # Now that I have the ONTS then we can look in the self.known_onts to build the table
        more_pages = False
        if ont_collection:
            self.alarms_table_widget.currentRow()
            row = ['ONT', 'Start', 'End', 'Duration', '#', 'Address', 'Latitude', 'Longitude']
            q_string_list = QStringList()
            for header_item in row:
                q_string_list.append(header_item.strip())
            # console_write("header = '%s'" % score_header)
            self.alarms_table_widget.setRowCount(0)
            self.alarms_table_widget.setColumnCount(len(row))
            # tool_table_widget = QtGui.QTableWidget(10, len(score_header))
            self.alarms_table_widget.setHorizontalHeaderLabels(q_string_list)
            self.alarms_table_widget.verticalHeader().setVisible(True)
            # self.ont_collection_table_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            # self.ont_collection_table_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self.alarms_table_widget.setShowGrid(True)
            self.alarms_table_widget.setSelectionBehavior(QAbstractItemView.SelectItems)
            if self.app:
                self.app.processEvents()
            page_num = 0
            self.alarm_load_label.setText('Loading pg 1, please wait...')
            self.abort = False
            self.browser_status_bar.showMessage("Calling API [query_post_query_alarms]")
            dd = self.eon_api_bridge.query_post_query_alarms(alarm_ids=list(ont_collection), p=page_num,
                                                             s=self.page_size)
            timeout_reset_value = self.eon_api_bridge.base_timeout
            while not dd and self.eon_api_bridge.status == "Timeout" and self.eon_api_bridge.base_timeout < 360:
                self.eon_api_bridge.base_timeout *= 2
                self.browser_status_bar.showMessage(
                    "doubling timeout value to %d sec" % self.eon_api_bridge.base_timeout)
                dd = self.eon_api_bridge.query_post_query_alarms(alarm_ids=list(ont_collection), p=page_num,
                                                                 s=self.page_size)
            if self.eon_api_bridge.base_timeout >= 360:
                self.browser_status_bar.showMessage(
                    "Timeout value is too great! (%d sec), giving up..." % self.eon_api_bridge.base_timeout)
                return
            self.eon_api_bridge.base_timeout = timeout_reset_value
            # ['ONT','Start','End','Duration','Address','Latitude','Longitude']
            if dd:
                self.browser_status_bar.showMessage('Number of items in page is %d' % dd['pageTotalItems'])
                alarm_list = []
                alarms = dd['alarms']
                for this_ont in alarms:
                    start_time_ms = this_ont["alarmReceiveTime"]  # 1435976727000
                    # Corrected for US Eastern time
                    start_time = str(arrow.get(start_time_ms/1000).to('US/Eastern').format('YYYY-MM-DD HH:mm:ss'))
                    # Using no timezone correction
                    # start_time = str(arrow.get(start_time_ms/1000).format('YYYY-MM-DD HH:mm:ss'))
                    end_time_ms = this_ont["alarmClearTime"]
                    if end_time_ms:
                        end_time = str(arrow.get(end_time_ms/1000).to('US/Eastern').format('YYYY-MM-DD HH:mm:ss'))
                        # end_time = str(arrow.get(end_time_ms/1000).format('YYYY-MM-DD HH:mm:ss'))
                        duration_time_ms = end_time_ms - start_time_ms
                        duration = "%6.2f" % (duration_time_ms/1000/60)  # This is in minutes
                    else:
                        end_time = ""
                        duration = "-1"
                    ont_address = this_ont["ontAddress"].split()

                    alarm_list.append([this_ont['ontSerialNumber'],  # "0011FE87",
                                       start_time,  # 1435976727000
                                       end_time,
                                       duration,
                                       ont_address[0],  # house number
                                       r' '.join(ont_address[1:-1]) +' '+ r','.join(ont_address[-1:]),
                                       "%f" % (this_ont["latitude"]),
                                       "%f" % (this_ont["longitude"])]
                                      )

                for this_row in alarm_list:
                    current_row = self.alarms_table_widget.rowCount()
                    self.alarms_table_widget.insertRow(current_row)
                    for col, this_item in enumerate(this_row):
                        item = QtGui.QTableWidgetItem(QString(this_item.strip()))
                        self.alarms_table_widget.setItem(current_row, col, item)
                if dd['pageTotalItems'] < self.page_size:
                    more_pages = False
                else:
                    more_pages = True
            # Loop here until no more utility components of the first collection are found
            while more_pages and dd is not None and not self.abort:
                page_num += 1
                self.alarm_load_label.setText('Loading pg %d of %d' % ((page_num + 1), (dd['totalPages'])))
                self.operation_progress_bar.setValue(((page_num + 1)*100)/(dd['totalPages']))
                # self.page_load_label.setText('Loading page %d of %d' % (page_num, (dd['totalPages']-1)))
                if self.app is not None:
                    self.app.processEvents()
                self.browser_status_bar.showMessage("Calling API [query_post_query_alarms]")
                dd = self.eon_api_bridge.query_post_query_alarms(alarm_ids=list(ont_collection), p=page_num,
                                                                 s=self.page_size)
                timeout_reset_value = self.eon_api_bridge.base_timeout
                while not dd and self.eon_api_bridge.status == "Timeout" and self.eon_api_bridge.base_timeout < 360:
                    self.eon_api_bridge.base_timeout *= 2
                    self.browser_status_bar.showMessage(
                        "doubling timeout value to %d sec" % self.eon_api_bridge.base_timeout)
                    dd = self.eon_api_bridge.query_post_query_alarms(alarm_ids=list(ont_collection), p=page_num,
                                                                     s=self.page_size)
                if self.eon_api_bridge.base_timeout >= 360:
                    self.browser_status_bar.showMessage(
                        "Timeout value is too great! (%d sec), giving up..." % self.eon_api_bridge.base_timeout)
                    return
                self.eon_api_bridge.base_timeout = timeout_reset_value
                if dd:
                    self.browser_status_bar.showMessage('Number of items in page is %d' % dd['pageTotalItems'])
                    alarm_list = []
                    alarms = dd['alarms']
                    for this_ont in alarms:

                        start_time_ms = this_ont["alarmReceiveTime"]  # 1435976727000
                        # Corrected for US Eastern time
                        start_time = str(arrow.get(start_time_ms/1000).to('US/Eastern').format('YYYY-MM-DD HH:mm:ss'))
                        # Using no timezone correction
                        # start_time = str(arrow.get(start_time_ms/1000).format('YYYY-MM-DD HH:mm:ss'))
                        end_time_ms = this_ont["alarmClearTime"]
                        if end_time_ms:
                            end_time = str(arrow.get(end_time_ms/1000).to('US/Eastern').format('YYYY-MM-DD HH:mm:ss'))
                            # end_time = str(arrow.get(end_time_ms/1000).format('YYYY-MM-DD HH:mm:ss'))
                            duration_time_ms = end_time_ms - start_time_ms
                            duration = "%6.2f" % (duration_time_ms/1000/60)  # This is in minutes
                        else:
                            end_time = ""
                            duration = "-1"
                        ont_address = this_ont["ontAddress"].split()
                        alarm_list.append([this_ont['ontSerialNumber'],  # "0011FE87",
                                           start_time,                   # 1435976727000
                                           end_time,
                                           duration,
                                           ont_address[0],  # house number
                                           r' '.join(ont_address[1:]),
                                           "%f" % (this_ont["latitude"]),
                                           "%f" % (this_ont["longitude"])]
                                          )
                    for this_row in alarm_list:
                        current_row = self.alarms_table_widget.rowCount()
                        self.alarms_table_widget.insertRow(current_row)
                        for col, this_item in enumerate(this_row):
                            item = QtGui.QTableWidgetItem(QString(this_item.strip()))
                            self.alarms_table_widget.setItem(current_row, col, item)
                    if 'pageTotalItems' not in dd.keys():
                        self.abort = True
                    self.browser_status_bar.showMessage('Number of items in page is %d' % dd['pageTotalItems'])
                    if dd['pageTotalItems'] < self.page_size:
                        more_pages = False
            if self.abort:
                self.show_cancel()
                self.alarm_load_label.setText('Aborted but loaded %d pages.' % (page_num + 1))
            else:
                self.alarm_load_label.setText('Done loading %d pages.' % (page_num + 1))
            self.operation_progress_bar.setValue(0)
            self.alarms_table_widget.resizeColumnsToContents()
            if self.enable_raw_sort.isChecked():
                self.alarms_table_widget.setSortingEnabled(True)
            else:
                self.alarms_table_widget.setSortingEnabled(False)
        else:
            self.browser_status_bar.showMessage("Select some ONT to get the raw alarms for selected ONTS")
    
    @pyqtSignature("")
    def on_stop_pushbutton_clicked(self):
        """
        Slot documentation goes here.
        """
        self.abort = True
    
    @pyqtSignature("")
    def on_collect_onts_pushbutton_clicked(self):
        """
        This action collects the ONTs that are selected from any of the ONT windows and
        puts them in the collection table
        """
        # Check for selected rows in either table
        self.on_clear_collection_pushbutton_clicked()
        self.ont_collection_table_widget.setSortingEnabled(False)
        self.ont_collection_table_widget.clearSelection()
        self.browser_status_bar.showMessage("Clearing the selection table")

        asset_items = self.assets_table_widget.selectedItems()
        ont_items = self.ont_table_widget.selectedItems()
        ont_collection1 = set()
        rows1 = set()
        ont_collection2 = set()
        rows2 = set()
        if asset_items or ont_items:
            if asset_items:
                for idx in self.assets_table_widget.selectedIndexes():
                    rows1.add(idx.row())
                for this_row in rows1:
                    onts = str(self.assets_table_widget.item(this_row, self.ONT_COLUMN).text())
                    ont_array = onts.split('|')
                    for this_ont in ont_array:
                        if this_ont:
                            if this_ont.find('PENDING') < 0:
                                ont_collection1.add(this_ont)
            if ont_items:
                for idx in self.ont_table_widget.selectedIndexes():
                    rows2.add(idx.row())
                for this_row in rows2:
                    this_ont = str(self.ont_table_widget.item(this_row, 0).text())
                    if this_ont:
                        if this_ont.find('PENDING') < 0:
                            ont_collection2.add(this_ont)

            ont_collection = ont_collection1 | ont_collection2
            # Now that I have the ONTS then we can look in the self.known_onts to build the table
            row = ['ONT', '#', 'Address', 'Latitude', 'Longitude']
            q_string_list = QStringList()
            for header_item in row:
                q_string_list.append(header_item.strip())
            # console_write("header = '%s'" % score_header)
            self.ont_collection_table_widget.setRowCount(0)
            self.ont_collection_table_widget.setColumnCount(len(row))
            # tool_table_widget = QtGui.QTableWidget(10, len(score_header))
            self.ont_collection_table_widget.setHorizontalHeaderLabels(q_string_list)
            self.ont_collection_table_widget.verticalHeader().setVisible(True)
            # self.ont_collection_table_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            # self.ont_collection_table_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self.ont_collection_table_widget.setShowGrid(True)
            self.ont_collection_table_widget.setSelectionBehavior(QAbstractItemView.SelectItems)

            for this_ont in ont_collection:
                if this_ont in self.known_onts.keys():
                    row = self.known_onts[this_ont]
                    current_row = self.ont_collection_table_widget.rowCount()
                    self.ont_collection_table_widget.insertRow(current_row)
                    item = QtGui.QTableWidgetItem(QString(this_ont))
                    self.ont_collection_table_widget.setItem(current_row, 0, item)
                    ont_address = row['ontAddress'].split()
                    item = QtGui.QTableWidgetItem(QString(ont_address[0]))
                    self.ont_collection_table_widget.setItem(current_row, 1, item)
                    item = QtGui.QTableWidgetItem(QString(r' '.join(ont_address[1:])))
                    self.ont_collection_table_widget.setItem(current_row, 2, item)
                    item = QtGui.QTableWidgetItem(QString('%f' % row['latitude']))
                    self.ont_collection_table_widget.setItem(current_row, 3, item)
                    item = QtGui.QTableWidgetItem(QString('%f' % row['longitude']))
                    self.ont_collection_table_widget.setItem(current_row, 4, item)

            self.ont_collection_table_widget.resizeColumnsToContents()
        else:
            self.browser_status_bar.showMessage(
                r'Highlight some items first from ONTs or ASSETS then click the collect button')
        if self.enable_collect_sort.isChecked():
            self.ont_collection_table_widget.setSortingEnabled(True)

    @pyqtSignature("")
    def on_clear_collection_pushbutton_clicked(self):
        """
        Slot documentation goes here.
        """
        self.browser_status_bar.showMessage("Clearing the selection table")
        self.ont_collection_table_widget.clearSelection()
        self.ont_collection_table_widget.setSortingEnabled(False)
        # self.ont_collection_table_widget.horizontalHeader().sortIndicatorSection()
        while self.ont_collection_table_widget.rowCount() > 0:
            self.ont_collection_table_widget.removeRow(0)
        self.ont_collection_table_widget.removeRow(0)
        self.ont_collection_table_widget.clear()
        if self.enable_collect_sort.isChecked():
            self.ont_collection_table_widget.setSortingEnabled(True)
        self.browser_status_bar.showMessage("Cleared the selection table")

    def clear_ont_table_widget(self):
        """
        Slot documentation goes here.
        """
        self.browser_status_bar.showMessage("Clearing the ont table")
        self.ont_table_widget.setSortingEnabled(False)
        self.ont_table_widget.clearSelection()
        while self.ont_table_widget.rowCount() > 0:
            self.ont_table_widget.removeRow(0)
        self.ont_table_widget.removeRow(0)

        self.ont_table_widget.clear()
        if self.enable_ont_sort.isChecked():
            self.ont_table_widget.setSortingEnabled(True)

        self.browser_status_bar.showMessage("Cleared the ont table")

    def clear_utility_asset_table(self):
        self.browser_status_bar.showMessage("Clearing the utility asset table")
        self.assets_table_widget.setSortingEnabled(False)
        self.assets_table_widget.clearSelection()

        while self.assets_table_widget.rowCount() > 0:
            self.assets_table_widget.removeRow(0)
        self.assets_table_widget.removeRow(0)

        self.assets_table_widget.clear()
        if self.enable_asset_sort.isChecked():
            self.assets_table_widget.setSortingEnabled(True)
        self.browser_status_bar.showMessage("Cleared the utility asset table")

    def clear_alarm_table(self):
        self.browser_status_bar.showMessage("Clearing the raw alarms table")
        self.alarms_table_widget.setSortingEnabled(False)
        self.alarms_table_widget.clearSelection()
        while self.alarms_table_widget.rowCount() > 0:
            self.alarms_table_widget.removeRow(0)
        self.alarms_table_widget.removeRow(0)
        self.alarms_table_widget.clear()
        if self.enable_raw_sort.isChecked():
            self.alarms_table_widget.setSortingEnabled(True)
        self.browser_status_bar.showMessage("Cleared the raw alarms table")

    @pyqtSignature("")
    def on_export_selected_alarms_pushbutton_clicked(self):
        """
        This is the EXPORT CSV button
        """
        if self.restrict_to_timespan_checkbox.isChecked():
            time_received = str(self.time_received_line_edit.text())
            time_completed = str(self.time_complete_line_edit.text())
            time_restriction = {'received': time_received,
                                'completed': time_completed,
                                'time_window': int(self.time_span_window.text())}
        else:
            time_restriction = None
        alarm_selection_items = self.alarms_table_widget.selectedItems()
        if alarm_selection_items:
            rows = set()
            for idx in self.alarms_table_widget.selectedIndexes():
                rows.add(idx.row())
            save_file_name = 'selected_' + str(self.export_directory_line_edit.text())
        else:
            rows = set(range(self.alarms_table_widget.rowCount()))
            save_file_name = str(self.export_directory_line_edit.text())

        if self.export_directory:
            save_file_name = self.export_directory + '/' + save_file_name
            try:
                os.mkdir(r'./' + self.export_directory)
            except WindowsError:
                print "directory exists"

        self.save_table(rows, save_file_name, time_restriction)

    @pyqtSignature("")
    def on_export_directory_line_edit_editingFinished(self):
        """
        Slot documentation goes here.
        """
        self.browser_status_bar.showMessage("Editing finished. Now save the results.")

    @pyqtSignature("")
    def on_actionPreferences_triggered(self):
        """
        Slot documentation goes here.
        """
        pass

    def save_table(self, rows, data_file_name='', restrict_time=None):
        # First find out if there was a value passed in, if not then use the default

        if data_file_name:
            this_file_name = data_file_name
        else:
            this_file_name = self.global_settings['DEFAULT_FILE_NAME']

        if this_file_name.find('(') > 0:
            if not restrict_time:
                this_file_name = this_file_name.replace('(','((ALL)')

        # Next find out if its just a filename
        split_file_parts = os.path.split(this_file_name)
        if split_file_parts[0]:
            # There was a directory given check to see if it exists
            file_name_path = split_file_parts[0]
            if os.path.isdir(split_file_parts[0]):
                self.browser_status_bar.showMessage("Directory exists")
            else:
                self.browser_status_bar.showMessage("Will make the directory %s" % split_file_parts[0])
        else:
            # see if there is a default file path
            if self.global_settings['DEFAULT_SAVE_LOCATION']:
                # see if its a directory
                if os.path.isdir(self.global_settings['DEFAULT_SAVE_LOCATION']):
                    # it is so lets use that
                    file_name_path = self.global_settings['DEFAULT_SAVE_LOCATION']
                else:
                    # use the relative directory
                    file_name_path = os.path.abspath('.')
            else:
                # There was no default save location so use the relative location
                file_name_path = os.path.abspath('.')


        # Next find out if the actual file name was given
        if split_file_parts[1]:
            # There was a filename specified so use it
            root_file_name = split_file_parts[1]
        else:
            # There was no filename specified so look check the default filename
            if self.global_settings['DEFAULT_FILE_NAME']:
                root_file_name = self.global_settings['DEFAULT_FILE_NAME']
            else:
                # We're is desperate straights so just create one
                root_file_name = 'os_exported_file.csv'

        # now check to see if there is a .csv file extension
        if root_file_name.find('.csv') == len(root_file_name)-4:
            file_extension = ''
        else:
            file_extension = '.csv'

        if restrict_time:
            # The time will be strings in this form: " 08/07/2015 11:31"
            try:
                target_start = arrow.get(restrict_time['received'], 'MM/DD/YYYY HH:mm').timestamp
            except arrow.parser.ParserError:
                try:
                    target_start = arrow.get(restrict_time['received'], 'M/DD/YYYY HH:mm').timestamp
                except arrow.parser.ParserError:
                    try:
                        target_start = arrow.get(restrict_time['received'], 'M/DD/YYYY H:mm').timestamp
                    except arrow.parser.ParserError:
                        try:
                            target_start = arrow.get(restrict_time['received'], 'MM/DD/YYYY H:mm').timestamp
                        except Exception as e:
                            print "problem parsing received time value %s, %s" % (restrict_time['received'], e)
                            target_start = 0
            try:
                target_end = arrow.get(restrict_time['completed'], 'MM/DD/YYYY HH:mm').timestamp
            except arrow.parser.ParserError:
                try:
                    target_end = arrow.get(restrict_time['completed'], 'M/DD/YYYY HH:mm').timestamp
                except arrow.parser.ParserError:
                    try:
                        target_end = arrow.get(restrict_time['completed'], 'M/DD/YYYY H:mm').timestamp
                    except arrow.parser.ParserError:
                        try:
                            target_end = arrow.get(restrict_time['completed'], 'MM/DD/YYYY H:mm').timestamp
                        except Exception as e:
                            print "problem parsing completion time value %s, %s" % (restrict_time['completed'], e)
                            target_end = arrow.get(arrow.utcnow()).timestamp

            # The value 3600*10 is the number of seconds in an hour * 10 hours. So the window is +/- 10 hours
            time_margin = restrict_time['time_window'] * 3600  # 3600*10
        # OK with all the parts create a filename
        filename = '%s/%s%s' % (file_name_path, root_file_name, file_extension)
        number_rows = self.alarms_table_widget.rowCount()
        if number_rows > 0:
            number_columns = self.alarms_table_widget.columnCount()
            if self.alarms_table_widget.horizontalHeaderItem(0).text():
                header_text_array = []
                for i in range(number_columns):
                    item_text = str(self.alarms_table_widget.horizontalHeaderItem(i).text())
                    header_text_array.append("%s" % item_text)
                try:
                    with open(filename, 'wb') as csv_file:
                        writer_object = csv.writer(csv_file, quoting=csv.QUOTE_MINIMAL)
                        writer_object.writerow(header_text_array)
                        for i in rows:
                            row = []
                            for j in range(number_columns):
                                item_text = self.alarms_table_widget.item(i, j).text()
                                row.append("%s" % item_text)

                            if restrict_time:
                                try:
                                    actual_start = arrow.get(row[header_text_array.index('Start')], 'YYYY-MM-DD HH:mm:ss').timestamp # '2015-07-20 12:27:42'
                                except arrow.parser.ParserError as e:
                                    try:
                                        actual_start = arrow.get(row[header_text_array.index('Start')], 'YYYY-MM-DD H:mm:ss').timestamp # '2015-07-20 12:27:42'
                                    except arrow.parser.ParserError as e:
                                        try:
                                            actual_start = arrow.get(row[header_text_array.index('Start')], 'YYYY-MM-DD HH:m:ss').timestamp # '2015-07-20 12:27:42'
                                        except arrow.parser.ParserError as e:
                                            try:
                                                actual_start = arrow.get(row[header_text_array.index('Start')], 'YYYY-MM-DD H:m:ss').timestamp # '2015-07-20 12:27:42'
                                            except Exception as e:
                                                print "problem parsing actual START time %s,  %s" % (row[header_text_array.index('Start')], e)
                                                continue

                                try:
                                    actual_end = arrow.get(row[header_text_array.index('End')], 'YYYY-MM-DD HH:mm:ss').timestamp # '2015-07-20 12:27:42'
                                except arrow.parser.ParserError as e:
                                    try:
                                        actual_end = arrow.get(row[header_text_array.index('End')], 'YYYY-MM-DD H:mm:ss').timestamp # '2015-07-20 12:27:42'
                                    except arrow.parser.ParserError as e:
                                        try:
                                            actual_end = arrow.get(row[header_text_array.index('End')], 'YYYY-MM-DD HH:m:ss').timestamp # '2015-07-20 12:27:42'
                                        except arrow.parser.ParserError as e:
                                            try:
                                                actual_end = arrow.get(row[header_text_array.index('End')], 'YYYY-MM-DD H:m:ss').timestamp # '2015-07-20 12:27:42'
                                            except Exception as e:
                                                print "problem parsing actual END time %s,  %s" % (row[header_text_array.index('End')], e)
                                                continue

                                if actual_start < target_start - time_margin:
                                    print "Alarm start was %s, relative to the target alarm start time, dropping." % \
                                          str((arrow.get(actual_start)-arrow.get(target_start)))
                                    continue
                                else:
                                    print "Alarm start (%s), target (%s) passes. Difference is %s." % (row[header_text_array.index('Start')],
                                                                                    restrict_time['received'],
                                                                                    str((arrow.get(actual_start)-arrow.get(target_start))))
                                if actual_end > target_end + time_margin:
                                    print "Alarm end was %s, relative to the target alarm end time, dropping." % \
                                          str((arrow.get(actual_end)-arrow.get(target_end)))
                                    continue
                                else:
                                    print "Alarm end (%s), target (%s) passes. Difference is %s. " % (row[header_text_array.index('End')],
                                                                                  restrict_time['completed'],
                                                                                  str((arrow.get(actual_end)-arrow.get(target_end))))

                            writer_object.writerow(row)
                except IOError as e:
                    self.browser_status_bar.showMessage("File is not writeable. Is it open? %s" % e)
        self.browser_status_bar.showMessage("File saved as %s" % filename)


    @pyqtSignature("")
    def on_assign_to_assets_clicked(self):
        """
        Slot documentation goes here.
        """

        alarm_selection_items = self.alarms_table_widget.selectedItems()
        if alarm_selection_items:
            rows = set()
            for idx in self.alarms_table_widget.selectedIndexes():
                rows.add(idx.row())

            filename = 'selected_' + str(self.export_directory_line_edit.text()).replace('.csv','') + '_assign_dump.csv'

        else:
            rows = set(range(self.alarms_table_widget.rowCount()))
            filename = str(self.export_directory_line_edit.text()).replace('.csv','') + '_assign_dump.csv'

        if self.export_directory:
            filename = self.export_directory + '/' + filename
            try:
                os.mkdir('./' + self.export_directory)
            except WindowsError:
                print "directory exists"

        self.browser_status_bar.showMessage("Dumping asset assignment of ONTs to file named: %s" % filename)
        alarm_ont_id_column = 0
        event_start_id_column = 1
        event_end_id_column = 2
        event_duration_id_column = 3
        #  asset_id_column = 0
        asset_address_column = [1, 2]
        asset_lat_column = 3
        asset_lon_column = 4
        header_text_array = ['ONT', 'Utility Asset', 'Address', 'Lat', 'Lon', 'Dist(MI)', 'Start', 'End',
                             'Duration(minutes)']

        with open(filename, 'wb') as csv_file:
            writer_object = csv.writer(csv_file, quoting=csv.QUOTE_MINIMAL)
            writer_object.writerow(header_text_array)
            for row in rows:  # xrange(self.alarms_table_widget.rowCount()):
                item = self.alarms_table_widget.item(row, alarm_ont_id_column)
                this_ont = str(item.text())
                for this_linked_asset in self.known_onts[this_ont]['linked_assets']:
                    if this_linked_asset:
                        asset_pointer = [(i, this_row.index(this_linked_asset)) for i, this_row in
                                         enumerate(self.asset_table_array) if this_linked_asset in this_row]
                        if asset_pointer:
                            # print "this ONT points to %d items" % len(asset_pointer)
                            asset_row = asset_pointer[0][0]
                            asset_id = this_linked_asset
                            street_num = self.asset_table_array[asset_row][asset_address_column[0]]
                            street_address = self.asset_table_array[asset_row][asset_address_column[1]]
                            if street_num and street_address:
                                asset_address = str(street_num) + ' ' + str(street_address)
                            else:
                                asset_address = ''
                            lat = self.asset_table_array[asset_row][asset_lat_column]
                            if lat:
                                asset_lat = str(lat)
                            else:
                                asset_lat = ''
                            lon = self.asset_table_array[asset_row][asset_lon_column]
                            if lon:
                                asset_lon = str(lon)
                            else:
                                asset_lon = ''
                            try:
                                if asset_lat != '' and asset_lon != '':
                                    distance_from_ont = lat_lon_distance(float(asset_lat),
                                                                         float(asset_lon),
                                                                         self.known_onts[this_ont]['latitude'],
                                                                         self.known_onts[this_ont]['longitude'])
                                else:
                                    distance_from_ont = -1
                            except Exception as e:
                                print "error = %s" % e
                                distance_from_ont = -1

                            event_start_item_text = self.alarms_table_widget.item(row, event_start_id_column).text()
                            if event_start_item_text:
                                event_start = str(event_start_item_text)
                            else:
                                event_start = ''
                            event_end_item_text = self.alarms_table_widget.item(row, event_end_id_column).text()
                            if event_end_item_text:
                                event_end = str(event_end_item_text)
                            else:
                                event_end = ''
                            event_duration_item_text = self.alarms_table_widget.item(row,
                                                                                     event_duration_id_column).text()
                            if event_duration_item_text:
                                event_duration = str(event_duration_item_text)
                            else:
                                event_duration = ''
                            row_text_array = [("'%s" % this_ont),
                                              asset_id,
                                              asset_address,
                                              asset_lat,
                                              asset_lon,
                                              ("%f" % distance_from_ont),
                                              event_start,
                                              event_end,
                                              event_duration
                                             ]
                            writer_object.writerow(row_text_array)
                            self.operation_progress_bar.setValue(row * 100 / self.alarms_table_widget.rowCount())

                            if self.app is not None:
                                self.app.processEvents()

                            if row < 10:
                                print "'%s| %s| %s| %s| %s| %s| %s| %s| %s" % \
                                    (this_ont,
                                     asset_id,
                                     asset_address,
                                     asset_lat,
                                     asset_lon,
                                     ("%f" % distance_from_ont),
                                     event_start,
                                     event_end,
                                     event_duration
                                    )
        self.operation_progress_bar.setValue(0)
        self.browser_status_bar.showMessage("Dump file written to: %s" % filename)

    @pyqtSignature("")
    def on_export_kml_clicked(self):
        """
        Slot documentation goes here.
        """
        # Create a single KML mark where the outage was reported.


        if self.restrict_to_radius_checkbox.isChecked():
            radius = float(str(self.ont_radius_line_edit.text()))
            lat_lon = str(self.ont_lat_lon_line_edit.text()).split(',')
            latitude = float(lat_lon[0])
            longitude = float(lat_lon[1])
            area_restriction = {'latitude': latitude, 'longitude': longitude, 'radius': radius}
        else:
            area_restriction = None

        if self.restrict_to_timespan_checkbox.isChecked():
            time_received = str(self.time_received_line_edit.text())
            time_completed = str(self.time_complete_line_edit.text())
            time_restriction = {'received': time_received,
                                'completed': time_completed,
                                'time_window': int(self.time_span_window.text())}
        else:
            time_restriction = None

        alarm_selection_items = self.alarms_table_widget.selectedItems()
        save_file_name = str(self.export_directory_line_edit.text())
        if save_file_name:
            this_file_name = save_file_name
        else:
            this_file_name = self.global_settings['DEFAULT_KML_FILE']

        # Next find out if its just a filename
        split_file_parts = os.path.split(this_file_name)

        # Next find out if the actual file name was given
        if split_file_parts[1]:
            # There was a filename specified so use it
            root_file_name = split_file_parts[1]
        else:
            # There was no filename specified so look check the default filename
            if self.global_settings['DEFAULT_KML_FILE']:
                root_file_name = self.global_settings['DEFAULT_KML_FILE']
            else:
                # We're is desperate straights so just create one
                root_file_name = 'outage_browser.kml'

        # now check to see if there is a .csv file extension
        if root_file_name.find('.csv') == len(root_file_name)-4:
            # yes so extract the base part of that name
            kml_filename = root_file_name[:-4] + '.kml'
            kml_ont_filename = root_file_name[:-4] + '_ont.kml'
            kml_asset_filename = root_file_name[:-4] + '_asset.kml'
            kml_outage_filename = root_file_name[:-4] + '_outage.kml'

        else:
            # just append a kml to the end
            kml_filename = root_file_name+'.kml'
            kml_ont_filename = root_file_name+ '_ont.kml'
            kml_asset_filename = root_file_name[:-4] + '_asset.kml'
            kml_outage_filename = root_file_name[:-4] + '_outage.kml'

        # Need to change from 5/11/2015 17:02
        # to this 
        this_outage_start = str(self.time_received_line_edit.text())
        this_outage_end = str(self.time_complete_line_edit.text())
        this_address = "%s, %s" % (str(self.address_line_edit.text()), str(self.city_state_line_edit.text()))
        make_kml_outage_marker(kml_outage_filename,
                               str(self.lat_lon_line_edit.text()),
                               street_address=this_address,
                               outage_start=this_outage_start,
                               outage_end=this_outage_end)

        if alarm_selection_items:
            kml_filename = 'selected_' + kml_filename

        # if self.export_directory:
        #     kml_filename = self.export_directory + os.sep + filename
        #     try:
        #         os.mkdir('.' + os.sep + self.export_directory)
        #     except WindowsError:
        #         print "directory exists"

        #####################################################
        # alarms on ONTs in region
        #####################################################
        number_rows = self.alarms_table_widget.rowCount()
        if number_rows > 0:
            number_columns = self.alarms_table_widget.columnCount()
            if self.alarms_table_widget.horizontalHeaderItem(0).text():
                header_text_array = []
                for i in range(number_columns):
                    item_text = str(self.alarms_table_widget.horizontalHeaderItem(i).text())
                    header_text_array.append("%s" % item_text)
                duration_index = header_text_array.index('Duration')
                try:
                    data_dict = []
                    if alarm_selection_items:
                        these_rows = self.alarms_table_widget.selectionModel().selectedRows()
                        for this_row in these_rows:
                            i = this_row.row()
                            if float(self.alarms_table_widget.item(i, duration_index).text()) > 0.0:
                                row_text_array = []
                                for j in range(number_columns):
                                    item_text = self.alarms_table_widget.item(i, j).text()
                                    row_text_array.append("%s" % item_text)
                                data_dict.append(row_text_array)
                    else:
                        for i in range(number_rows):
                            # Test to see if the outage time was not 0.0
                            if float(self.alarms_table_widget.item(i, duration_index).text()) > 0.0:
                                row_text_array = []
                                for j in range(number_columns):
                                    item_text = self.alarms_table_widget.item(i, j).text()
                                    row_text_array.append("%s" % item_text)
                                data_dict.append(row_text_array)
                    saved_name = make_kml(data_header=header_text_array, data_dict=data_dict,
                                          unique_file_name=kml_filename, restrict_area=area_restriction,
                                          restrict_time=time_restriction)
                    self.browser_status_bar.showMessage("KML file saved to %s" % saved_name)
                except Exception as e:
                    print "problem making KML file because %s" % e

        #####################################################
        # ONTs (eligibilities) in region
        #####################################################
        number_rows = self.ont_table_widget.rowCount()
        if number_rows > 0:
            number_columns = self.ont_table_widget.columnCount()
            if self.ont_table_widget.horizontalHeaderItem(0).text():
                header_text_array = []
                for i in range(number_columns):
                    item_text = str(self.ont_table_widget.horizontalHeaderItem(i).text())
                    header_text_array.append("%s" % item_text)
                try:
                    data_dict = []
                    if alarm_selection_items:
                        these_rows = self.ont_table_widget.selectionModel().selectedRows()
                        for this_row in these_rows:
                            i = this_row.row()
                            row_text_array = []
                            for j in range(number_columns):
                                item_text = self.ont_table_widget.item(i, j).text()
                                row_text_array.append("%s" % item_text)
                            data_dict.append(row_text_array)
                    else:
                        for i in range(number_rows):
                            # Test to see if the outage time was not 0.0
                            row_text_array = []
                            for j in range(number_columns):
                                item_text = self.ont_table_widget.item(i, j).text()
                                row_text_array.append("%s" % item_text)
                            data_dict.append(row_text_array)

                    saved_name = make_kml_ont_eligibilities(data_header=header_text_array, data_dict=data_dict,
                                                            unique_file_name=kml_ont_filename,
                                                            restrict_area=area_restriction)
                except Exception as e:
                    print "problem making ONT KML file because %s" % e
        #  At this point the ONTs are collected so now the nearest assets to these ONTs should be collected and used.
        #####################################################
        # Utility Assets in region
        #####################################################
        number_rows = self.assets_table_widget.rowCount()
        if number_rows > 0:
            number_columns = self.assets_table_widget.columnCount()
            if self.assets_table_widget.horizontalHeaderItem(0).text():
                header_text_array = []
                for i in range(number_columns):
                    item_text = str(self.assets_table_widget.horizontalHeaderItem(i).text())
                    header_text_array.append("%s" % item_text)
                try:
                    data_dict = []
                    if alarm_selection_items:
                        these_rows = self.assets_table_widget.selectionModel().selectedRows()
                        for this_row in these_rows:
                            i = this_row.row()
                            row_text_array = []
                            for j in range(number_columns):
                                item_text = self.assets_table_widget.item(i, j).text()
                                row_text_array.append("%s" % item_text)
                            data_dict.append(row_text_array)
                    else:
                        for i in range(number_rows):
                            # Test to see if the outage time was not 0.0
                            row_text_array = []
                            for j in range(number_columns):
                                item_text = self.assets_table_widget.item(i, j).text()
                                row_text_array.append("%s" % item_text)
                            data_dict.append(row_text_array)

                    saved_name = make_kml_utility_assets(data_header=header_text_array, data_dict=data_dict,
                                                         unique_file_name=kml_asset_filename,
                                                         restrict_area=area_restriction)

                except Exception as e:
                    print "problem making ASSET KML file because %s" % e

    @pyqtSignature("")
    def on_enable_raw_sort_clicked(self):
        """
        Slot documentation goes here.
        """
        if self.enable_raw_sort.isChecked():
            self.alarms_table_widget.setSortingEnabled(True)
        else:
            self.alarms_table_widget.setSortingEnabled(False)

    @pyqtSignature("")
    def on_enable_asset_sort_clicked(self):
        """
        Slot documentation goes here.
        """
        if self.enable_asset_sort.isChecked():
            self.assets_table_widget.setSortingEnabled(True)
        else:
            self.assets_table_widget.setSortingEnabled(False)

    @pyqtSignature("")
    def on_enable_ont_sort_clicked(self):
        """
        Slot documentation goes here.
        """
        if self.enable_ont_sort.isChecked():
            self.ont_table_widget.setSortingEnabled(True)
        else:
            self.ont_table_widget.setSortingEnabled(False)

    @pyqtSignature("")
    def on_enable_collect_sort_clicked(self):
        """
        Slot documentation goes here.
        """
        if self.enable_collect_sort.isChecked():
            self.ont_collection_table_widget.setSortingEnabled(True)
        else:
            self.ont_collection_table_widget.setSortingEnabled(False)

    @pyqtSignature("")
    def on_clear_ont_select_clicked(self):
        """
        Slot documentation goes here.
        """
        self.ont_table_widget.clearSelection()

    @pyqtSignature("")
    def on_clear_collect_select_clicked(self):
        """
        Slot documentation goes here.
        """
        self.ont_collection_table_widget.clearSelection()

    @pyqtSignature("")
    def on_clear_utility_selection_clicked(self):
        """
        Slot documentation goes here.
        """
        self.assets_table_widget.clearSelection()

    def collect_alarm_file_set(self):
        """

        """
        if self.start_time_dirty or self.end_time_dirty:
            self.start_time_dirty = False
            self.end_time_dirty = False
            self.alarms_dir = self.source_base + os.sep + self.source_dir
            utc = arrow.utcnow()
            start_timestamp = utc.strptime('20' + self.start_time['year'] + self.start_time['month'] +
                                           self.start_time['day'] + self.start_time['hour'] +
                                           self.start_time['minute'], '%Y%m%d%H%M', 'US/Eastern')
            stop_timestamp = utc.strptime('20' + self.end_time['year'] + self.end_time['month'] +
                                          self.end_time['day'] + self.end_time['hour'] +
                                          self.end_time['minute'], '%Y%m%d%H%M', 'US/Eastern')

            # note that utc.timestamp will provide the times needed to call the API
            # local = utc.to('US/Eastern')
            # the_date = '%d' % the_timestamp
            self.browser_status_bar.showMessage("Building alarm file set!")
            if self.app is not None:
                self.app.processEvents()
            file_names = os.listdir(self.alarms_dir)
            self.alarm_files = set()
            for f in file_names:
                # alarm_files.add(f)
                if f.startswith('pon_eon_alarms'):
                    parts = f.split('.')
                    sub_parts = parts[0].split('_')
                    # format of the alarm file is: 'pon_eon_alarms_0112150830.txt'
                    date_string_part = sub_parts[3]
                    mo = date_string_part[0:2]
                    dd = date_string_part[2:4]
                    yy = date_string_part[4:6]
                    hh = date_string_part[6:8]
                    mn = date_string_part[8:10]
                    this_timestamp = utc.strptime('20' + yy + mo + dd + hh + mn, '%Y%m%d%H%M', 'US/Eastern')
                    if (this_timestamp > start_timestamp) and (this_timestamp <= stop_timestamp):
                        self.alarm_files.add(f)
                        print "File: %s added to the search list." % f

    def grep_os(self, the_string, filename):
        grep_cmd = 'C:/Progra~2/Git/bin/grep.exe'
        # filename = r'C:/repo/Aptect/Verizon/Workproduct/EON-IOT/Replayer/ClientDataCleaner/alarms_2015/may/*.txt'
        if filename.find('.txt') > 0:
            cmd_string = grep_cmd + ' "' + the_string.strip() + '" ' + filename
        else:
            cmd_string = grep_cmd + ' "' + the_string.strip() + '" ' + filename + '/*.txt'
        values = subprocess.Popen(cmd_string, stdout=subprocess.PIPE).stdout.read()
        return values.strip().split('\n')

    @pyqtSignature("")
    def on_find_alarm_files_bushbutton_clicked(self):
        """
        Slot documentation goes here.
        """
        self.collect_alarm_file_set()
        search_term = str(self.ont_search_string_text.text())  # '44098675'
        if search_term:
            self.browser_status_bar.showMessage("Searching for %s" % search_term)
            records = []
            if self.app is not None:
                self.app.processEvents()
            # records = [{'line':'', 'file_name':''}]
            # raw_path = "%r" % filename
            filename = self.source_base + os.sep + self.source_dir
            new_filename = filename.replace('\\', "/")
            use_multigrep = False
            if use_multigrep:
                # Multigrep is a method of looking for multiple instances using the grep command itself.
                # See http://www.cyberciti.biz/faq/searching-multiple-words-string-using-grep/
                # Example
                #    $ grep 'warning\|error\|critical' /var/log/messages
                # In this case the number of items must be limited to make sure the grep command is not
                # longer than what grep can handle.
                pass
            else:
                if self.restrict_to_timespan_checkbox.isChecked():
                    for this_file in self.alarm_files:
                        single_file = new_filename + '/' + this_file
                        print "Searching in: %s for all alarms with ONT number: %s" % (single_file, search_term)
                        the_values = self.grep_os(search_term, single_file)
                        for this_value in the_values:
                            if len(this_value) > 0:
                                source_file = single_file.replace(new_filename + '/','')
                                records.append(source_file + ':' + this_value)  # + '|' + source_file)
                else:
                    print "Searching in: %s for all alarms with ONT number: %s" % (new_filename, search_term)
                    the_values = self.grep_os(search_term, new_filename)
                    for this_value in the_values:
                        if len(this_value) > 0:
                            records.append(this_value.replace(new_filename + '/', ''))

            self.alarm_files_combo_box.clear()
            for this_record in records:
                this_item = QString(this_record.strip())
                self.alarm_files_combo_box.addItem(this_item)

            # pon_eon_alarms_0601150130

            # for f in sorted(self.alarm_files):
            #     self.browser_status_bar.showMessage("Searching in %s. Found %d matches." % (f, match_count))
            #     if self.app is not None:
            #         self.app.processEvents()
            #     if self.abort:
            #         self.abort = False
            #         break
            #     for i, line in enumerate(open(self.alarms_dir + os.sep + f, 'r')):
            #         if re.search(search_term, line):
            #             if line:
            #                 records.append([f, i, line])
            #                 match_count += 1
            # self.alarm_files_combo_box.clear()
            # if records:
            #     for i in range(len(records)):
            #         this_string = ("%s, line %d: %s" % (records[i][0], records[i][1], records[i][2])).strip()
            #         this_item = QString(this_string)
            #         self.alarm_files_combo_box.addItem(this_item)
            self.browser_status_bar.showMessage("Found %d matches." % len(records))
        else:
            self.browser_status_bar.showMessage("Enter a search term in the search box first")

    @pyqtSignature("")
    def on_start_date_time_edit_editingFinished(self):
        """
        Slot documentation goes here.
        """
        this_year = self.start_date_time_edit.date().year()
        if this_year == 2014:
            alarm_dir = os.sep + r'alarms_2014'
            year_str = '14'
        elif this_year == 2015:
            alarm_dir = os.sep + r'alarms_2015'
            year_str = '15'
        else:
            self.browser_status_bar.showMessage("Only 2014 or 2015 is allowed")
            return

        this_month = self.start_date_time_edit.date().month()
        if this_month == 1:
            self.source_dir = r'ClientDataCleaner' + alarm_dir + os.sep + r'jan'
            month_str = '01'
        elif this_month == 2:
            self.source_dir = r'ClientDataCleaner' + alarm_dir + os.sep + r'feb'
            month_str = '02'
        elif this_month == 3:
            self.source_dir = r'ClientDataCleaner' + alarm_dir + os.sep + r'mar'
            month_str = '03'
        elif this_month == 4:
            self.source_dir = r'ClientDataCleaner' + alarm_dir + os.sep + r'apr'
            month_str = '04'
        elif this_month == 5:
            self.source_dir = r'ClientDataCleaner' + alarm_dir + os.sep + r'may'
            month_str = '05'
        elif this_month == 6:
            self.source_dir = r'ClientDataCleaner' + alarm_dir + os.sep + r'jun'
            month_str = '06'
        elif this_month == 7:
            self.source_dir = r'ClientDataCleaner' + alarm_dir + os.sep + r'jul'
            month_str = '07'
        elif this_month == 8:
            self.source_dir = r'ClientDataCleaner' + alarm_dir + os.sep + r'aug'
            month_str = '08'
        elif this_month == 9:
            self.source_dir = r'ClientDataCleaner' + alarm_dir + os.sep + r'sep'
            month_str = '09'
        elif this_month == 10:
            self.source_dir = r'ClientDataCleaner' + alarm_dir + os.sep + r'oct'
            month_str = '10'
        elif this_month == 11:
            self.source_dir = r'ClientDataCleaner' + alarm_dir + os.sep + r'nov'
            month_str = '11'
        elif this_month == 12:
            self.source_dir = r'ClientDataCleaner' + alarm_dir + os.sep + r'dec'
            month_str = '12'
        else:
            self.browser_status_bar.showMessage("Only Jan through Dec is allowed")
            return

        this_day = self.start_date_time_edit.date().day()
        day_str = "%02d" % this_day
        this_hour = self.start_date_time_edit.time().hour()
        hour_str = "%02d" % this_hour
        this_minute = self.start_date_time_edit.time().minute()
        minute_str = "%02d" % int(floor((float(this_minute)/60.0) * 4.0) * 15)

        self.start_time = {'month': month_str,
                           'day': day_str,
                           'year': year_str,
                           'hour': hour_str,
                           'minute': minute_str}
        self.start_time_dirty = True

    @pyqtSignature("")
    def on_end_date_time_edit_editingFinished(self):
        """
        Slot documentation goes here.
        """
        this_year = self.end_date_time_edit.date().year()
        if this_year == 2014:
            alarm_dir = os.sep + r'alarms_2014'
            year_str = '14'
        elif this_year == 2015:
            alarm_dir = os.sep + r'alarms_2015'
            year_str = '15'
        else:
            self.browser_status_bar.showMessage("Only 2014 or 2015 is allowed")
            return

        this_month = self.end_date_time_edit.date().month()
        if this_month == 1:
            self.source_dir = r'ClientDataCleaner' + alarm_dir + os.sep + r'jan'
            month_str = '01'
        elif this_month == 2:
            self.source_dir = r'ClientDataCleaner' + alarm_dir + os.sep + r'feb'
            month_str = '02'
        elif this_month == 3:
            self.source_dir = r'ClientDataCleaner' + alarm_dir + os.sep + r'mar'
            month_str = '03'
        elif this_month == 4:
            self.source_dir = r'ClientDataCleaner' + alarm_dir + os.sep + r'apr'
            month_str = '04'
        elif this_month == 5:
            self.source_dir = r'ClientDataCleaner' + alarm_dir + os.sep + r'may'
            month_str = '05'
        elif this_month == 6:
            self.source_dir = r'ClientDataCleaner' + alarm_dir + os.sep + r'jun'
            month_str = '06'
        elif this_month == 7:
            self.source_dir = r'ClientDataCleaner' + alarm_dir + os.sep + r'jul'
            month_str = '07'
        elif this_month == 8:
            self.source_dir = r'ClientDataCleaner' + alarm_dir + os.sep + r'aug'
            month_str = '08'
        elif this_month == 9:
            self.source_dir = r'ClientDataCleaner' + alarm_dir + os.sep + r'sep'
            month_str = '09'
        elif this_month == 10:
            self.source_dir = r'ClientDataCleaner' + alarm_dir + os.sep + r'oct'
            month_str = '10'
        elif this_month == 11:
            self.source_dir = r'ClientDataCleaner' + alarm_dir + os.sep + r'nov'
            month_str = '11'
        elif this_month == 12:
            self.source_dir = r'ClientDataCleaner' + alarm_dir + os.sep + r'dec'
            month_str = '12'
        else:
            self.browser_status_bar.showMessage("Only Jan through Dec is allowed")
            return

        this_day = self.end_date_time_edit.date().day()
        this_hour = self.end_date_time_edit.time().hour()
        hour_str = "%02d" % this_hour
        this_minute = self.end_date_time_edit.time().minute()
        rounded_minute = int(ceil((float(this_minute)/60.0) * 4.0) * 15)
        if rounded_minute == 60:
            rounded_minute = 0
            this_day += 1
        minute_str = "%02d" % rounded_minute
        day_str = "%02d" % this_day

        self.end_time = {'month': month_str,
                         'day': day_str,
                         'year': year_str,
                         'hour': hour_str,
                         'minute': minute_str}
        self.end_time_dirty = True
    
    @pyqtSignature("")
    def on_filter_for_duration_clicked(self):
        """
        Slot documentation goes here.
        """
        # TODO: not implemented yet
        print "Not implemented yet"

    def show_cancel(self):
        cancel_notice = QMessageBox.information(
            self,
            self.tr("API Cancelled"),
            self.tr("""The ReST API was aborted. Operation was cancelled."""),
            QMessageBox.StandardButtons(
                QMessageBox.Ok),
            QMessageBox.Ok)
        print "cancel notice %d" % int(cancel_notice)
    
    @pyqtSignature("int")
    def on_feeder_combo_box_currentIndexChanged(self, index):
        """
        Slot documentation goes here.
        """
        feeder = str(self.feeder_combo_box.currentText())
        filename = str(self.export_directory_line_edit.text())
        f_parts_1 = filename.split('(')
        if len(f_parts_1) > 1:
            f_part_1 = f_parts_1[0]
            f_parts_2 = filename.split(')')
            if len(f_parts_2) > 1:
                f_part_2 = f_parts_2[1]
                filename = f_part_1 + '(' + feeder + ')' + f_part_2
                self.export_directory_line_edit.setText(filename)
    
    @pyqtSignature("QPoint")
    def on_ont_table_widget_customContextMenuRequested(self, pos):
        """
        Slot documentation goes here.
        """
        print "slot callback"

    def copy_table(self):

        selected = self.ont_table_widget.selectedRanges()
        vertical_header_here = False
        if selected != []:
            s = '\t'+"\t".join([str(self.ont_table_widget.horizontalHeaderItem(i).text())
                                for i in xrange(selected[0].leftColumn(), selected[0].rightColumn()+1)])
            s += '\n'
            for r in xrange(selected[0].topRow(), selected[0].bottomRow()+1):
                try:
                    s += self.ont_table_widget.verticalHeaderItem(r).text() + '\t'
                    vertical_header_here = True
                except AttributeError:
                    pass
                    # print "No vertical header for this row"
                for c in xrange(selected[0].leftColumn(), selected[0].rightColumn()+1):
                    try:
                        s += str(self.ont_table_widget.item(r,c).text()) + "\t"
                    except AttributeError:
                        s += "\t"
                s = s[:-1] + "\n" #eliminate last '\t'
            if not vertical_header_here:
                # Remove the extra tab if there were no vertical headers found
                s = s[1:]
            self.clip.setText(s)
    
    @pyqtSignature("")
    def on_actionCut_activated(self):
        """
        Slot documentation goes here.
        """
        # TODO: not implemented yet
        print "Cut selection"
    
    @pyqtSignature("")
    def on_actionCopy_activated(self):
        """
        Slot documentation goes here.
        """
        # TODO: not implemented yet
        print "copy select"
    
    @pyqtSignature("")
    def on_actionPaste_activated(self):
        """
        Slot documentation goes here.
        """
        # TODO: not implemented yet
        print "paste selection"
    
    @pyqtSignature("")
    def on_mark_raw_events_pushbutton_clicked(self):
        """
        Slot documentation goes here.
        """
        # These magic number are the column number of the self.ont_table_widget
        STREET_NUM_COL = 1
        ADDRESS_COL = 2
        LATITUDE_COL = 3
        LONGITUDE_COL = 4
        DISTANCE_COL = 5

        alarm_count = 0
        ont_count = 0
        selected = self.ont_table_widget.selectedRanges()
        if selected != []:
            status = "Done!"
            for r in xrange(selected[0].topRow(), selected[0].bottomRow()+1):
                self.operation_progress_bar.setValue((r * 100)/(selected[0].bottomRow()+1))
                c = 0
                try:
                    ont_id = str(self.ont_table_widget.item(r,c).text())
                except AttributeError:
                    ont_id = ''
                self.ont_search_string_text.setText(QString(ont_id))
                self.on_find_alarm_files_bushbutton_clicked()
                if len(self.alarm_files_combo_box) > 0:
                    ont_count += 1
                    alarm_count += len(self.alarm_files_combo_box)
                    # Set the color of this row to be green
                    item = self.ont_table_widget.item(r,c)  # QtGui.QTableWidgetItem('Text')
                    item.setBackground(QColor(0, 255, 0))
                    # collect the alarm events now
                    self.raw_event_collection[ont_id] = []

                    target_start = arrow.get(str(self.time_received_line_edit.text()), 'MM/DD/YYYY HH:mm').timestamp
                    for i in range(len(self.alarm_files_combo_box)):
                        this_item_text = str(self.alarm_files_combo_box.itemText(i))
                        # Remove the extra OND_ID item in the text string
                        this_item_text = this_item_text.replace(':%s' % ont_id, '')
                        # 60216738|pon_eon_alarms_0530152315.txt:60216738|PKSKNYPSOL2*LET-4*19*1*14|5|PWR-LOS|2015-05-30 23:05:25.931|2015-05-30 23:06:16.000|::ONT
                        parts = this_item_text.split('|')
                        start_time_string = parts[4]  # This is the first time field in teh string
                        start_time = arrow.get(start_time_string, 'YYYY-MM-DD HH:mm:ss.SSS').timestamp  # '2015-07-20 17:53:10'
                        time_offset = start_time - target_start
                        # Add in the other items from the ONT table to enable easy export below.
                        this_item_text += "|%s" % str(self.ont_table_widget.item(r, STREET_NUM_COL).text())
                        this_item_text += "|%s" % str(self.ont_table_widget.item(r, ADDRESS_COL).text())
                        this_item_text += "|%s" % str(self.ont_table_widget.item(r, LATITUDE_COL).text())
                        this_item_text += "|%s" % str(self.ont_table_widget.item(r, LONGITUDE_COL).text())
                        this_item_text += "|%s" % str(self.ont_table_widget.item(r, DISTANCE_COL).text())
                        this_item_text += "|%f" % (time_offset / 3600.0)
                        self.raw_event_collection[ont_id].append(this_item_text)

                if self.abort:
                    self.show_cancel()
                    status = "Aborted!"

            self.browser_status_bar.showMessage("%s %d ONTs have alarm events, %d total alarms" %
                                                (status, ont_count, alarm_count))
            self.abort = False
            self.operation_progress_bar.setValue(0)
        else:
            self.browser_status_bar.showMessage("No Rows selected to mark! Select some rows or columns on the ont_table_widget first.")

    @pyqtSignature("")
    def on_clear_raw_events_pushbutton_clicked(self):
        """
        Slot documentation goes here.
        """
        selected = self.ont_table_widget.selectedRanges()
        if selected != []:
            for r in xrange(selected[0].topRow(), selected[0].bottomRow()+1):
                c = 0
                item = self.ont_table_widget.item(r,c)  # QtGui.QTableWidgetItem('Text')
                if item.backgroundColor().green() == 255 :
                    item.setBackground(QColor(255, 255, 255))
                    ont_id = str(item.text())
                    self.raw_event_collection[ont_id] = []
            self.browser_status_bar.showMessage("Selected rows cleared.")
        else:
            self.browser_status_bar.showMessage("Select rows to clear in the ONT table first then click the clear button!")

    @pyqtSignature("")
    def on_dump_raw_event_pushbutton_clicked(self):
        """
        Slot documentation goes here.
        """
        filename = 'raw_alarms_dump_file.csv'
        if self.export_directory:
            save_file_name = self.export_directory + '/' + filename
            try:
                os.mkdir(r'./' + self.export_directory)
            except WindowsError:
                print "directory exists"
        else:
            save_file_name = filename

        header_text_array = ['ONT', 'Filename', 'Equipment',
                             'Condition', 'Type', 'OFF', 'ON',
                             'Description', 'Street Num', 'Address',
                             'LAT', 'LON', 'Distance', 'Time Offset (hr)']
        try:
            with open(save_file_name, 'wb') as csv_file:
                writer_object = csv.writer(csv_file, quoting=csv.QUOTE_MINIMAL)
                writer_object.writerow(header_text_array)

                for this_ont in self.raw_event_collection.keys():
                    for i in range(len(self.raw_event_collection[this_ont])):
                        s = "%s|%s" % (this_ont, self.raw_event_collection[this_ont][i])
                        print "%s" % s
                        this_row=s.split('|')
                        writer_object.writerow(this_row)
            self.browser_status_bar.showMessage("Raw dump file created in %s" % filename)

        except IOError as e:
            self.browser_status_bar.showMessage("Raw dump file is not writeable. Is it open in Excel? %s" % e)

