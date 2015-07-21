# -*- coding: utf-8 -*-

"""
Module implementing MainWindow.
"""

from PyQt4.QtCore import pyqtSignature, QStringList, QString
from PyQt4.QtGui import QMainWindow, QAbstractItemView, QPalette, QColor, QLabel

from PyQt4 import QtGui

from Ui_outage_browser import Ui_MainWindow
from lat_lon_distance import lat_lon_distance
from make_kml_onts_function import make_kml
import g_config
import g_eon_api_bridge
import json
import arrow
import logging
import logging.handlers
import os
import datetime
import csv

unique_str = datetime.datetime.now().isoformat().replace(':', '_').replace('.', '_').replace('-', '_')
LOG_FILENAME = '.' + os.sep + 'ob_'+unique_str+'.log'
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

        self.working_radius = 0.75  # This will hold the radius
        self.eon_api_bridge = g_eon_api_bridge.EonApiBridge()
        self.asset_table_array = [[]]
        self.page_size = 100
        self.app = app
        self.abort = False
        self.known_onts = {}  # This will be a dictionary of known ONTs that can be selected
        self.ONT_COLUMN = 6  # The column of the asset table that contains the ONT array string
        self.global_settings = {'DEFAULT_SAVE_LOCATION': './',
                                'DEFAULT_FILE_NAME': 'RAW_ALARMS',
                                'DEFAULT_KML_FILE': 'groomer_browser'}
        self.operation_progress_bar.setValue(0)
        self.operation_progress_bar.setFixedHeight(10)

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
        """
        self.browser_status_bar.showMessage("parse job data")
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
            self.job_number_line_edit.setText(job_data_array[0])
            self.num_customer_line_edit.setText(job_data_array[1])
            self.time_received_line_edit.setText(job_data_array[2])
            self.time_complete_line_edit.setText(job_data_array[3])
            self.address_line_edit.setText(job_data_array[4])

            filename = job_data_array[4].replace(' ', '_').lower() + '_alarms.csv'
            self.export_directory_line_edit.setText(filename)

            self.city_state_line_edit.setText(job_data_array[5])
            feeder_name = job_data_array[8]
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
            self.lat_lon_line_edit.setText(job_data_array[9]+', '+job_data_array[10])
            self.ms_plate_line_edit.setText(job_data_array[11])
            # Also load the ont item list
            self.ont_lat_lon_line_edit.setText(job_data_array[9]+', '+job_data_array[10])
            self.ont_radius_line_edit.setText('%3.2f' % self.working_radius)
            # Clear all the default values
            self.asset_table_array = [[]]
            self.known_onts = {}
            self.on_clear_collection_pushbutton_clicked()
            self.clear_utility_asset_table()
            self.clear_ont_table_widget()
            self.clear_alarm_table()
            filename = job_data_array[4].replace(' ','_') + '_ALARMS.csv'
            self.export_directory_line_edit.setText(filename)

    @pyqtSignature("")
    def on_get_utility_assets_by_feeder_clicked(self):
        """
        Slot documentation goes here.
        """
        # call this API http://10.123.0.27:8080/eon360/api/utilities/circuits/SPROUT?p=3&s=200
        this_circuit_id = str(self.feeder_combo_box.currentText())

        self.browser_status_bar.showMessage("get utility data assets for feeder = %s" % this_circuit_id)
        page_num = 0
        self.page_load_label.setText('Loading pg 1, please wait...')
        if self.app is not None:
            self.app.processEvents()
        more_pages = False
        self.browser_status_bar.showMessage(
            ("get utility data assets for feeder = %s [utilities_get_eon_utility_circuit_by_id_66 API]" %
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
            self.browser_status_bar.showMessage("Calling utilities_get_utilities_circuits_circuit_id API")
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
            self.eon_api_bridge.base_timeout = timeout_reset_value
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
                            self.known_onts[this_ont['ontSerialNumber']]['linked_assets'].append(this_item['transformerID'])
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
        self.browser_status_bar.showMessage("get onts in area")
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
            self.browser_status_bar.showMessage("Calling query_post_eon_data_30 API")
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
                self.browser_status_bar.showMessage("doubling timeout value to %d sec" % self.eon_api_bridge.base_timeout)
                dd = self.eon_api_bridge.query_post_query(query_parameter=query_parameter)
            self.eon_api_bridge.base_timeout = timeout_reset_value
            if dd:
                self.browser_status_bar.showMessage("Got a result")
                self.browser_status_bar.showMessage('Number of items in page is %d' % dd['eligibility']['pageTotalItems'])
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
                self.browser_status_bar.showMessage("Calling query_post_query API")
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
                    self.browser_status_bar.showMessage("doubling timeout value to %d sec" % self.eon_api_bridge.base_timeout)
                    dd = self.eon_api_bridge.query_post_query(query_parameter=query_parameter)
                self.eon_api_bridge.base_timeout = timeout_reset_value
                if dd:
                    self.browser_status_bar.showMessage("Got a result")
                    self.browser_status_bar.showMessage('Number of items in page is %d' % dd['eligibility']['pageTotalItems'])
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
                    for this_ont in ont_array:
                        row = this_ont
                        current_row = self.ont_table_widget.rowCount()
                        self.ont_table_widget.insertRow(current_row)
                        for col, this_item in enumerate(row):
                            item = QtGui.QTableWidgetItem(QString(this_item.strip()))
                            self.ont_table_widget.setItem(current_row, col, item)
            if self.abort:
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
            self.browser_status_bar.showMessage("Calling query_post_alarm_data_31 API")
            dd = self.eon_api_bridge.query_post_query_alarms(alarm_ids=list(ont_collection), p=page_num,
                                                              s=self.page_size)
            timeout_reset_value = self.eon_api_bridge.base_timeout
            while not dd and self.eon_api_bridge.status == "Timeout" and self.eon_api_bridge.base_timeout < 360:
                self.eon_api_bridge.base_timeout *= 2
                self.browser_status_bar.showMessage("doubling timeout value to %d sec" % self.eon_api_bridge.base_timeout)
                dd = self.eon_api_bridge.query_post_query_alarms(alarm_ids=list(ont_collection), p=page_num,
                                                                  s=self.page_size)
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
                self.browser_status_bar.showMessage("Calling query_post_query_alarms API")
                dd = self.eon_api_bridge.query_post_query_alarms(alarm_ids=list(ont_collection), p=page_num,
                                                                  s=self.page_size)
                timeout_reset_value = self.eon_api_bridge.base_timeout
                while not dd and self.eon_api_bridge.status == "Timeout" and self.eon_api_bridge.base_timeout < 360:
                    self.eon_api_bridge.base_timeout *= 2
                    self.browser_status_bar.showMessage("doubling timeout value to %d sec" % self.eon_api_bridge.base_timeout)
                    dd = self.eon_api_bridge.query_post_query_alarms(alarm_ids=list(ont_collection), p=page_num,
                                                                      s=self.page_size)
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

                self.browser_status_bar.showMessage('Number of items in page is %d' % dd['pageTotalItems'])
                if dd['pageTotalItems'] < self.page_size:
                    more_pages = False

            if self.abort:
                self.alarm_load_label.setText('Abort: Loaded %d pages.' % (page_num + 1))
            else:
                self.alarm_load_label.setText('Done: Loaded %d pages.' % (page_num + 1))
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
                            if this_ont.find('PENDING')<0:
                                ont_collection1.add(this_ont)
            if ont_items:
                for idx in self.ont_table_widget.selectedIndexes():
                    rows2.add(idx.row())
                for this_row in rows2:
                    this_ont = str(self.ont_table_widget.item(this_row, 0).text())
                    if this_ont:
                        if this_ont.find('PENDING')<0:
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
            self.browser_status_bar.showMessage("Select some items first from ONTs or ASSETS then click the collect button")
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
        Slot documentation goes here.
        """
        rows = set()
        for idx in self.alarms_table_widget.selectedIndexes():
            rows.add(idx.row())
        save_file_name = str(self.export_directory_line_edit.text())
        self.save_table(rows, save_file_name)

    @pyqtSignature("")
    def on_export_directory_line_edit_editingFinished(self):
        """
        Slot documentation goes here.
        """
        self.browser_status_bar.showMessage("editing finished, save the results")

    @pyqtSignature("")
    def on_actionPreferences_triggered(self):
        """
        Slot documentation goes here.
        """
        # TODO: not implemented yet
        pass

    def save_table(self, rows, data_file_name=''):
        # First find out if there was a value passed in, if not then use the default

        if data_file_name:
            this_file_name = data_file_name
        else:
            this_file_name = self.global_settings['DEFAULT_FILE_NAME']

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

        # OK with all the parts create a filename
        filename = '%s%s%s' % (file_name_path, root_file_name, file_extension)
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
                            row_text_array = []
                            for j in range(number_columns):
                                item_text = self.alarms_table_widget.item(i,j).text()
                                row_text_array.append("%s" % item_text)
                            writer_object.writerow(row_text_array)
                except IOError as e:
                    self.browser_status_bar.showMessage("File is not writeable. Is it open?")
    
    @pyqtSignature("")
    def on_assign_to_assets_clicked(self):
        """
        Slot documentation goes here.
        """
        alarm_ont_id_column = 0
        event_start_id_column = 1
        event_end_id_column = 2
        event_duration_id_column = 3
        asset_id_column = 0
        asset_address_column = [1,2]
        asset_lat_column = 3
        asset_lon_column = 4
        header_text_array = ['ONT', 'Utility Asset', 'Address', 'Lat', 'Lon', 'Dist(MI)', 'Start', 'End', 'Duration(minutes)']
        filename = str(self.job_number_line_edit.text()).replace(' ', '_') + '_assign_dump.csv'
        self.browser_status_bar.showMessage("Dumping asset assignment of ONTs to file named: %s" % filename)
        with open(filename, 'wb') as csv_file:
            writer_object = csv.writer(csv_file, quoting=csv.QUOTE_MINIMAL)
            writer_object.writerow(header_text_array)
            for row in xrange(self.alarms_table_widget.rowCount()):
                item = self.alarms_table_widget.item(row, alarm_ont_id_column)
                this_ont = str(item.text())
                for this_linked_asset in self.known_onts[this_ont]['linked_assets']:
                    if this_linked_asset != []:
                        asset_pointer = [(i, this_row.index(this_linked_asset)) for i, this_row in enumerate(self.asset_table_array) if this_linked_asset in this_row]
                        if asset_pointer != []:
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

                            event_start_item_text=self.alarms_table_widget.item(row, event_start_id_column).text()
                            if event_start_item_text:
                                event_start = str(event_start_item_text)
                            else:
                                event_start = ''
                            event_end_item_text = self.alarms_table_widget.item(row, event_end_id_column).text()
                            if event_end_item_text:
                                event_end = str(event_end_item_text)
                            else:
                                event_end = ''
                            event_duration_item_text = self.alarms_table_widget.item(row, event_duration_id_column).text()
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
                            if row < 10:
                                print "'%s| %s| %s| %s| %s| %s| %s| %s| %s" % \
                                    (("'%s" % this_ont),
                                      asset_id,
                                      asset_address,
                                      asset_lat,
                                      asset_lon,
                                      ("%f" % distance_from_ont),
                                      event_start,
                                      event_end,
                                      event_duration
                                     )
                            if self.app is not None:
                                self.app.processEvents()
        self.operation_progress_bar.setValue(0)
        self.browser_status_bar.showMessage("Dump file written to: %s" % filename)

    @pyqtSignature("")
    def on_export_kml_clicked(self):
        """
        Slot documentation goes here.
        """
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
            kml_filename = root_file_name[:-4]+'.kml'
        else:
            # just append a kml to the end
            kml_filename = root_file_name+'.kml'

        alarm_selection_items = self.alarms_table_widget.selectedItems()
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
                    data_dict =[]
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
                    saved_name = make_kml(data_header=header_text_array, data_dict=data_dict, unique_file_name=kml_filename)
                    self.browser_status_bar.showMessage("File saved to %s" % saved_name)
                except Exception as e:
                    print "problem making KML file because %s" % e
    
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
