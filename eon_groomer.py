#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) 2014, 2015 Patrick Moran for Verizon
#
# Distributes WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License. If not, see <http://www.gnu.org/licenses/>.

from collections import deque
import g_config
import g_eon_api_bridge
# from g_graphics import plot_assets
import time
import logging
import json
from g_lat_lon_distance import lat_lon_distance, move_to_lat_lon, compute_resolution
from sortedcontainers import SortedDict
import pickle
import copy
import pandas
from numpy import int64, fmax, argsort, array, interp, linspace, diff, random
import arrow

import Queue
import os
import threading

ON = 1
OFF = 0


class GroomingMessageHandler(threading.Thread):
    def __init__(self,
                 incoming_q,
                 incoming_queue_lock,
                 outgoing_q,
                 outgoing_queue_lock,
                 module_instance_name='Unnamed',
                 shared_data=None, shared_data_lock=None):

        self.incoming_rabbit_mq = incoming_q
        self.incoming_queue_lock = incoming_queue_lock
        self.outgoing_q = outgoing_q
        self.outgoing_queue_lock = outgoing_queue_lock

        self.my_local_logger = logging.getLogger(module_instance_name)
        self.my_local_logger.setLevel(logging.DEBUG)

        self.local_q = deque()
        self.eon_api_bridge = g_eon_api_bridge.EonApiBridge()
        self.handle_queue = False
        self.instance_name = module_instance_name
        # This is used to run the main loop
        self.run_enable = True

        self.shared_data = shared_data
        self.shared_data_lock = shared_data_lock

        self.start_time = 0
        self.run_start_time = time.time()
        self.groomer_state = "0:IDLE"  # Used to determine the current state of this thread in a multi-threaded env
        self.groom_run_state = "0:IDLE"  # Used to determine the current run mode of this thread
        self.idle_count = 0
        self.end_time = 0
        self.query_count = 0
        self.asset_dictionary = {}
        self.working_radius = g_config.START_RADIUS  # This will hold the radius units 0.12
        self.cell_collection_set = set()
        self.resolution = compute_resolution(self.working_radius)
        self.cell_count = 0
        self.utility_region = g_config.UTILITY_REGION
        self.ttl = g_config.TTL_MAX
        self.SHOW_PLOTS = False
        self.cell_time_event = False
        threading.Thread.__init__(self)

    @staticmethod
    def check_message_payload(dequeued_item):
        """
        This method checks that the message payload keys matches the required (specified) keys
        :return: False is any key is missing otherwise True
        """
        key_array = ["dateTime",
                     "payload",
                     "messageType"]

        # Note that the "ttl" key (and others) may be present but its not checked here!

        for key in key_array:
            if key not in dequeued_item.keys():
                return False

        key_array = ["zoomR",
                     "spatial",
                     "circuitID",
                     "reputationEnabled",
                     "assetID",
                     "temporal",
                     "outageTime",
                     "company",
                     "votes",
                     "zoomT",
                     "longitude",
                     "latitude"]
        for key in key_array:
            if key not in dequeued_item["payload"].keys():
                return False
        return True

    def process_incoming_rabbit_mq(self):
        """
        Processes the Rabbit MQ bus messages and process the queue depending on the type
        If the type is Query then put it on the local queue for processing later
        """
        self.groomer_state = "3:PROCESS QUEUE"
        lock_counter = 0
        while not self.incoming_queue_lock.acquire(False):
            self.my_local_logger.debug("Trying to acquire lock. Sleeping  0.05s.")
            time.sleep(g_config.SLEEP_TIME)
            lock_counter += 1
            if lock_counter > 100:
                self.my_local_logger.debug("Cant acquire incoming queue lock, returning")
                self.my_local_logger.error("Unable to acquire lock in process_incoming_queue, returning!")
                self.groomer_state = "4:PROCESS QUEUE LOCK ERROR"
                return
        while not self.incoming_rabbit_mq.empty():
            self.my_local_logger.debug(
                "Groomer says Incoming Rabbit MQ not empty, length is %d" % self.incoming_rabbit_mq.qsize())
            self.my_local_logger.debug("Acquired lock")
            # This is where the incoming grooming message is pulled off the Rabbit MQ.
            dequeued_item = self.incoming_rabbit_mq.get()
            if self.check_message_payload(dequeued_item):
                self.my_local_logger.info("A %s type message was dequeued " %
                                          dequeued_item['messageType'])
            else:
                self.my_local_logger.error("Message payload is malformed in process_incoming_queue, returning")
                if self.incoming_queue_lock:
                    self.incoming_queue_lock.release()
                    self.my_local_logger.debug("GROOMER rabbit MQ lock was released")
                    self.my_local_logger.info("The rabbit MQ lock was released")
                self.groomer_state = "5:PROCESS QUEUE MALFORMED"
                return
            # Determine what is queue command type is and dispatch it.
            if dequeued_item['messageType'] == 'Test':
                # This is a dummy Test which is dropped for now.
                pass
            elif dequeued_item['messageType'] == 'Clear':
                # Restore the previous results
                pass
            elif dequeued_item['messageType'] == 'Save':
                # Save the current groom (filter) settings and kick off a new Utility wide groom process

                # Grab the Query message type and stuff it in a local fifo queue
                self.my_local_logger.debug("Save type message received")
                self.my_local_logger.debug("query_guid = %s" % "None - missing on save")  # dequeued_item['queryGuid'])
                #######################################################
                # Collect interesting payload information here
                #######################################################
                if "ttl" not in dequeued_item.keys():
                    dequeued_item["ttl"] = g_config.TTL_UTILITY_SPAN
                self.local_q.append(dequeued_item)
                self.my_local_logger.debug("Message queued to the local incoming queue (len=%d)" % len(self.local_q))
                self.my_local_logger.info("Message queued to the local incoming queue (len=%d)" % len(self.local_q))
                pass
            elif dequeued_item['messageType'] == 'Query':
                # Grab the Query message type and stuff it in a local fifo queue
                self.my_local_logger.debug("Query type message received")
                self.my_local_logger.debug("query_guid = %s" % dequeued_item['queryGuid'])
                #######################################################
                # Collect interesting payload information here
                #######################################################
                if "ttl" not in dequeued_item.keys():
                    dequeued_item["ttl"] = g_config.TTL_MAX
                self.local_q.append(dequeued_item)
                self.my_local_logger.debug("Message queued to the local incoming queue (len=%d)" % len(self.local_q))
                self.my_local_logger.info("Message queued to the local incoming queue (len=%d)" % len(self.local_q))
            else:
                self.my_local_logger.error("incoming_rabbit_mq TYPE is a UNKNOWN")
        if self.incoming_queue_lock:
            self.incoming_queue_lock.release()
            self.my_local_logger.debug("GROOMER rabbit MQ lock was released")
            self.my_local_logger.info("The rabbit MQ lock was released")
        self.my_local_logger.debug("process_incoming_rabbit_mq finished")
        self.groomer_state = "0:IDLE"

    def get_data_in_cell_area(self, cell_parameters, ttl):
        """
        Ask the EON API for onts, circuits and transformers for a given lat, lon and radius
        Returns a group of items that are inside the circle with a given center (lat, lon) and
        radius.
        Note: convert the time units in the ONT event list into minutes by dividing by 60000
        :param cell_parameters: Latitude
        :param ttl: The time to live.
        :return: this_cell # A hexagonal cell dictionary

            this_cell = {'neighbors': [],  # the 6 nearest neighbor cells
                    'assets': {}, # The utility assets including their lat and lon and events
                    'onts': {}, # Verizon's ONTs including their lat and lon and events
                    'state': '' # A string representing the state of this cell.
                                    This is used for multi threading purposes so that neighboring cells can see
                                    whats going on.
                    'circuits': {} # This is a set of circuits in this cell. All assets on a circuit
                                     are in the circuits list
                    'lat_lon': [] # The lat and lon array of the center of the cell
                    'radius': 1.00 # The radius of the circumscribed cell.
         ont_items is a dictionary of {'lat_lon':[],'assets':[],'events':[]}
         asset_items is a dictionary of {'lat_lon':[],'onts':[],'events':[]}
         circuit_items is a dictionary of  {'connected_items' , asset_item_key}
            where asset_item_key is a key entry in the asset_item dictionary
            events is an array of 2 sets of events. events[0] is the "fail_time" and events[1] is the "restore_time"
         A call to teh API is done in a loop to gather all items, here is a test of teh api call:
         The swagger test example is
          http://10.123.0.27:8080/eon360/api/query
         With a json payload of
            {
              "itemType":"ALL",
              "circle": {
                "unit": "MILES",
                "longitude": -73.8773389,
                "radius": 1.0,
                "latitude": 41.2693778
              },
              "pageParameter": {
                "page": 0,
                "size": 100
              }
            }
        This will return a data structure like this
        dd['eligibility']['dataItems']
        dd['alarm']['dataItems']
        dd['utility']['dataItems']
        """

        # query_guid = payload["query_guid"]
        this_lat = cell_parameters["latitude"]
        this_lon = cell_parameters["longitude"]
        # utility = cell_parameters["company"]
        groom_time = cell_parameters["outageTime"]
        # circuit_id = cell_parameters["circuitID"]
        # asset_id = cell_parameters["assetID"]
        # votes = cell_parameters["votes"]
        # spatial = cell_parameters["spatial"]
        # temporal = cell_parameters["temporal"]
        # reputation_ena = cell_parameters["reputationEnabled"]
        # zoom_t = cell_parameters["zoomT"]
        # zoom_r = cell_parameters["zoomR"]
        this_radius = cell_parameters["radius"]
        # units = cell_parameters["units"]

        query_type = "ALL"

        ont_serial_number_set = set()
        ont_items = {}

        asset_serial_number_set = set()
        asset_items = {}

        circuit_serial_number_set = set()
        circuit_items = {}
        # The six neighbor cells are initially set to be empty
        # This a string quid and an angle (in degrees)
        neighbor_array = [["", 0], ["", 60], ["", 120], ["", 180], ["", 240], ["", 300]]
        this_cell = {'neighbors': neighbor_array,
                     'assets': {},
                     'onts': {},
                     'circuits': {},
                     'state': 'creating',
                     'lat_lon': [this_lat, this_lon],
                     'radius': this_radius,
                     'groom_time': groom_time,
                     'ttl': 0
                     }
        page_number = 0
        page_size = 20
        query_parameter = json.dumps({"itemType": query_type,
                                      "circle": {"longitude": this_lon,
                                                 "latitude": this_lat,
                                                 "radius": this_radius, "unit": g_config.RADIUS_UNITS},
                                      "pageParameter": {"page": page_number, "size": page_size}})
        self.my_local_logger.debug("Formed query parameter: %s" % query_parameter)
        dd = self.eon_api_bridge.query_post_eon_data_30(query_parameter=query_parameter)
        more_pages = True
        # Loop here until no more utility components of the first collection are found
        while more_pages and dd is not None:
            # This is the ONTs loop through them and find all the ONTs in the area
            for this_ont in dd['eligibility']['dataItems']:
                ont_dictionary_keyword = this_ont['ontSerialNumber']
                ont_serial_number_set.add(ont_dictionary_keyword)
                if ont_dictionary_keyword == "[PENDING INSTALL]":
                    self.my_local_logger.debug("skipping this ont in eligibility list")
                    continue
                ont_items[ont_dictionary_keyword] = {'lat_lon': [this_ont['latitude'], this_ont['longitude']]}
                alarm_set_time = set()
                alarm_clear_time = set()
                ont_items[ont_dictionary_keyword]['events'] = [alarm_set_time, alarm_clear_time]
                ont_items[ont_dictionary_keyword]['assets'] = set()

            for this_alarm in dd['alarm']['dataItems']:
                alarm_dictionary_keyword = this_alarm['ontSerialNumber']
                if alarm_dictionary_keyword not in ont_serial_number_set:
                    if alarm_dictionary_keyword == "[PENDING INSTALL]":
                        self.my_local_logger.debug("skipping this ONT in the alarm list")
                        continue
                    ont_serial_number_set.add(alarm_dictionary_keyword)
                    ont_items[alarm_dictionary_keyword] = {'lat_lon': [this_alarm['latitude'], this_alarm['longitude']]}
                    alarm_set_time = set()
                    alarm_clear_time = set()
                    ont_items[alarm_dictionary_keyword]['events'] = [alarm_set_time, alarm_clear_time]
                    ont_items[alarm_dictionary_keyword]['assets'] = set()

                if this_alarm['alarmReceiveTime']:
                    alarm_set = float(this_alarm['alarmReceiveTime'])  # * 1e-3) / 60
                    ont_items[alarm_dictionary_keyword]['events'][0].add(alarm_set)

                if this_alarm['alarmClearTime']:
                    alarm_clear = float(this_alarm['alarmClearTime'])  # * 1e-3) / 60
                    ont_items[alarm_dictionary_keyword]['events'][1].add(alarm_clear)

            # Now go through the assets and associate the assets to the ONTs and the ONTs to the assets
            for this_item in dd['utility']['dataItems']:
                asset_dictionary_keyword = this_item['transformerID']
                if asset_dictionary_keyword not in asset_serial_number_set:
                    asset_serial_number_set.add(asset_dictionary_keyword)
                    asset_items[asset_dictionary_keyword] = {'lat_lon': [this_item['latitude'], this_item['longitude']]}
                    asset_items[asset_dictionary_keyword]['events'] = [set(), set()]
                    asset_items[asset_dictionary_keyword]['onts'] = set()
                    asset_items[asset_dictionary_keyword]['guid'] = this_item['guid']
                    asset_items[asset_dictionary_keyword]['serviceAddress'] = this_item['serviceAddress']
                    for this_ont in this_item['eligibilityList']:
                        ont_dictionary_keyword = this_ont['ontSerialNumber']
                        if ont_dictionary_keyword not in ont_serial_number_set:
                            ont_serial_number_set.add(ont_dictionary_keyword)
                            ont_items[ont_dictionary_keyword] = {
                                'lat_lon': [this_ont['latitude'], this_ont['longitude']]}
                            alarm_set_time = set()
                            alarm_clear_time = set()
                            ont_items[ont_dictionary_keyword]['events'] = [alarm_set_time, alarm_clear_time]
                            ont_items[ont_dictionary_keyword]['assets'] = set()
                        # Skip the ONTs that don't have an installation.
                        if ont_dictionary_keyword == "[PENDING INSTALL]":
                            self.my_local_logger.debug("skipping the ONT listed on eligibility list in asset_id=%s" %
                                                       asset_dictionary_keyword)
                            self.my_local_logger.info("Skipping %s because it's status is PENDING INSTALL" %
                                                      asset_dictionary_keyword)
                            continue
                        # Stitch up the assets in the onts
                        ont_items[ont_dictionary_keyword]['assets'].add(asset_dictionary_keyword)
                        # Stitch up the onts in the assets
                        asset_items[asset_dictionary_keyword]['onts'].add(ont_dictionary_keyword)

                circuit_dictionary_keyword = this_item['circuitID']
                if circuit_dictionary_keyword not in circuit_serial_number_set:
                    # add the circuit item to the circuit_serial_number_set is needed
                    circuit_serial_number_set.add(circuit_dictionary_keyword)
                    # and create an empty set
                    circuit_items[circuit_dictionary_keyword] = {'connected_items': set()}
                # Now add the data structure to the set
                circuit_items[circuit_dictionary_keyword]['connected_items'].add(asset_dictionary_keyword)

            ###########################
            # Look for the next page  #
            ###########################
            if (dd['utility']['pageTotalItems'] == page_size) or \
                    (dd['alarm']['pageTotalItems'] == page_size) or \
                    (dd['eligibility']['pageTotalItems'] == page_size):
                self.my_local_logger.debug("Collecting next page for this message")
                page_number += 1
                more_pages = True
                query_parameter = json.dumps({"itemType": query_type,
                                              "circle": {"longitude": this_lon,
                                                         "latitude": this_lat,
                                                         "radius": this_radius,
                                                         "unit": g_config.RADIUS_UNITS},
                                              "pageParameter": {"page": page_number, "size": page_size}})
                dd = self.eon_api_bridge.query_post_eon_data_30(query_parameter=query_parameter)
            else:
                more_pages = False
        this_cell['assets'] = asset_items
        # Go over the ONT set and see it there are any that don't have alarms. This might happen if there were no alarms
        # posted to this ONT because the main alarm injestion loop failed for some reason. There will still be alarms
        # that are posted on the ONTs and those can be recovered here.
        for this_ont in ont_items:
            if len(ont_items[this_ont]['events'][0]) == 0 or len(ont_items[this_ont]['events'][1]) == 0:
                # To find any ONTs that don't seem to have alarms make this call:
                # where ONT_SERIAL_NUMBER is 00ABB96 in this example.
                # http://10.123.0.27:8080/eon360/api/alarms?sortBy=alarmReceiveTime&ontSerialNumber=000ABB96&p=0&s=20
                dd = self.eon_api_bridge.alarm_get_pons_nms_00(ont_serial_number=this_ont)
                if dd:
                    if 'alarms' in dd.keys():
                        for this_alarm in dd['alarms']:
                            if this_alarm['alarmReceiveTime']:
                                alarm_set = float(this_alarm['alarmReceiveTime'])  # * 1e-3) / 60
                                ont_items[this_ont]['events'][0].add(alarm_set)
                                self.my_local_logger.info("Adding an AlarmReceiveTime to the data")
                            if this_alarm['alarmClearTime']:
                                alarm_clear = float(this_alarm['alarmClearTime'])  # * 1e-3) / 60
                                ont_items[this_ont]['events'][1].add(alarm_clear)
                    else:
                        self.my_local_logger.warning("No alarms found in call to alarm_get_pons_nms_00(ont_serial_number=%s)" % this_ont )
                else:
                    self.my_local_logger.warning("Nothing returned from the API call")
        this_cell['onts'] = ont_items
        this_cell['circuits'] = circuit_items
        this_cell['state'] = 'populated'
        this_cell['ttl'] = ttl
        self.my_local_logger.info("This CELL (radius= %3.3f %s @ lat=%f, lon=%f) has %d circuits, %d assets and %d onts." %
                                  (this_radius, g_config.RADIUS_UNITS, this_lat, this_lon,
                                   len(circuit_items), len(asset_items), len(ont_items))
                                  )



        # Note convert the time units into minutes by dividing by 60000
        return this_cell

    @staticmethod
    def persist_cell_pickle(cell, filename=""):
        """
        :param cell:  The cell structure that is persisted to disk
        :return:
        """
        this_lat = cell['lat_lon'][0]
        this_lon = cell['lat_lon'][1]
        if this_lat < 0:
            lat_str = ("%03.2f" % (float(round(-this_lat * 100)) / 100.0)).replace('.', 'm')
        else:
            lat_str = ("%03.2f" % (float(round(this_lat * 100)) / 100.0)).replace('.', 'p')
        if this_lon < 0:
            lon_str = ("%03.2f" % (float(round(-this_lon * 100)) / 100.0)).replace('.', 'm')
        else:
            lon_str = ("%03.2f" % (float(round(this_lon * 100)) / 100.0)).replace('.', 'p')

        if filename == "":
            filename = 'cell_' + lat_str + '_' + lon_str
        filename += '.pck'
        full_path = g_config.BASE_DIR + os.sep + g_config.PICKLES + os.sep + filename
        with open(full_path, "w") as f:  # write mode
            pickle.dump(cell, f)

    @staticmethod
    def un_persist_cell_pickle(this_lat, this_lon):
        """
        :param this_lat:
        :param this_lon:
        :return: cell
        """
        if this_lat < 0:
            lat_str = ("%03.2f" % (float(round(-this_lat * 100)) / 100.0)).replace('.', 'm')
        else:
            lat_str = ("%03.2f" % (float(round(this_lat * 100)) / 100.0)).replace('.', 'p')
        if this_lon < 0:
            lon_str = ("%03.2f" % (float(round(-this_lon * 100)) / 100.0)).replace('.', 'm')
        else:
            lon_str = ("%03.2f" % (float(round(this_lon * 100)) / 100.0)).replace('.', 'p')

        filename = 'cell_' + lat_str + '_' + lon_str + '.pck'
        with open(filename, "r") as f:  # read mode
            cell = pickle.load(open(f))
        return cell

    def temporal_filter(self, cell):
        """
        :param cell:

        This method does the filter model of the ont and returns a filtered outage based on the
        alarm_condition (a value between 0 and 1)
        Start with the alarm_condition =0 which is no alarm (These are alarm_conditions for ALARMs)
        This is how the EPOCH number can be converted back and forth to a date.

        In this context ON means power is ON, OFF means power is off
          t is in milliseconds. To convert to minutes divide by 1000 and by 60.

        :return:
        """
        self.cell_time_event = False
        for this_ont in cell['onts']:
            event_vector = {'t': [int64(g_config.ENGINE_BEGIN_TIME)], 'a': [ON]}
            on_times = cell['onts'][this_ont]['events'][ON]
            off_times = cell['onts'][this_ont]['events'][OFF]
            if len(on_times) > 0:
                for this_alarm in on_times:
                    event_vector['t'].append(this_alarm)
                    event_vector['a'].append(ON)

            if len(off_times) > 0:
                for this_alarm in off_times:
                    event_vector['t'].append(this_alarm)
                    event_vector['a'].append(OFF)

            # At this point we have a temporal vector of event for this ONT.
            time_vector = array(event_vector['t'])
            ind = argsort(time_vector)
            power_state = array(event_vector['a'])[ind]
            t = time_vector[ind]

            # At this point the sorted time and alarm vectors are ready

            # tw = t[t > t[-1] - config.ALARM_DETECT_WINDOW * 1000]
            # aw = a[t > t[-1] - config.ALARM_DETECT_WINDOW * 1000]

            # Deglitch the vectors now
            # To deglitch the time vector take all the values that at ON and extend them by 5 minutes then
            # and add (or) them back to the time vector

            # time_of_alarm_condition = tw[-1]  # The last time vector point (the sorted value)
            # alarm_condition = aw[-1]
            time_count = len(t)
            deglitched_power_state = copy.copy(power_state)

            # see for example http://pandas.pydata.org/pandas-docs/stable/timeseries.html
            for i in range(time_count - 1):
                if power_state[i] == OFF and power_state[i + 1] == ON:
                    if t[i + 1] < t[i] + g_config.DEGLITCH_TIME:
                        self.my_local_logger.debug(
                            "Deglitched the power at %s" % (pandas.to_datetime(t[i], unit='ms')))
                        deglitched_power_state[i] = ON
                    else:
                        self.my_local_logger.debug("off time is %f min (%f hours) (days %f)" % (
                            (t[i + 1] - t[i]) / 1000 / 60, (t[i + 1] - t[i]) / 1000 / 60 / 60,
                            (t[i + 1] - t[i]) / 1000 / 60 / 60 / 24))
            power_state_array = []
            time_array = []
            for i in range(time_count-1):
                time_array.append(t[i])
                time_array.append(t[i+1] - g_config.MS_TIME_RESOLUTION)  # something around 5 seconds
                power_state_array.append(deglitched_power_state[i])
                power_state_array.append(deglitched_power_state[i])
                if deglitched_power_state[i] == ON:
                    self.my_local_logger.debug("power on at %s" % (pandas.to_datetime(t[i], unit='ms')))
                if deglitched_power_state[i] == OFF:
                    self.my_local_logger.debug("power off at %s" % (pandas.to_datetime(t[i], unit='ms')))
            time_array.append(t[-1])
            power_state_array.append(deglitched_power_state[-1])

            sample_time = cell['groom_time']
            if sample_time > t[-1]:
                self.my_local_logger.debug(
                    "sample time is after the end of time in the time event list, using interpolated value")
                time_array.append(sample_time - g_config.MS_TIME_RESOLUTION)
                power_state_array.append(deglitched_power_state[-1])

            time_array_sec = [round(x / 1000) for x in time_array]
            # time_domain_vector = [time_array, power_state_array]  # column_stack((time_array,power_state_array))

            # Calculate a +/- 1 week interval every 5 minutes from the groom time unless the groom time is the same as
            # the current time then the last 30 minutes are used to compute the time vector.
            # This is done to allow the real time groomer to run a bit faster than the interactive groomer during the
            # interp call.

            # The arrow library produces timestamp values in seconds.
            current_time = arrow.utcnow().to('US/Eastern')
            a_week_ago = current_time.replace(weeks=-1)

            sample_time_arrow = arrow.get(sample_time/1000)
            if sample_time_arrow.timestamp < a_week_ago.timestamp:
                # This is a grooming operation that fits in the 2 week span of time.
                start_time = sample_time_arrow.replace(weeks=-1)
                stop_time = sample_time_arrow.replace(weeks=1)
            else:
                start_time = sample_time_arrow.replace(weeks=-2)
                stop_time = sample_time_arrow

            # The time vector will be in seconds
            # One minute  = 60
            # One hour  = 60*60
            # One day = 24*60*60
            # One week = 7*24*60*60
            # Five minute intervals are 5*60

            delta_time = 5*60  # This is the sample interval of the time vector (Every 5 minutes)
            number_of_points = (stop_time.timestamp - start_time.timestamp) / delta_time
            sample_time_array = linspace(start_time.timestamp, stop_time.timestamp, number_of_points)
            sample_power_array = interp(sample_time_array, time_array_sec, power_state_array)
            time_domain_vector = [sample_time_array, sample_power_array]
            reliability = sum(sample_power_array)/len(sample_power_array)
            event_durations = []
            event_times = []
            if sample_power_array.min() == sample_power_array.max():
                self.SHOW_PLOTS = False
            else:
                self.SHOW_PLOTS = True
            if self.SHOW_PLOTS:
                if not g_config.IS_DEPLOYED:
                    print "Reliability = %4.4f" % reliability
                if reliability > 0.8:
                    self.cell_time_event = True
                    if not g_config.IS_DEPLOYED:
                        try:
                            import matplotlib.pyplot as plt
                            # plt.plot(time_array, power_state_array, 'o')
                            plt.plot(sample_time_array, sample_power_array, '-x')
                            plt.show(block=False)
                        except:
                            print "Something went wrong with the matplotlib command, skipping!"

                    if (sample_power_array[0] > 0) and (sample_power_array[-1] > 0):
                        if not g_config.IS_DEPLOYED:
                            print "Diff the time vector to find the on and off times."
                        diff_sample_power_array = diff(sample_power_array)
                        index_on = diff_sample_power_array > 0
                        on_times = sample_time_array[index_on]
                        index_off = diff_sample_power_array < 0
                        off_times = sample_time_array[index_off]
                        if len(on_times) == len(off_times):
                            for k, t_off in enumerate(off_times):
                                # The power will be off from the time it turns minus the time it turned off.
                                power_fail_event_duration = on_times[k] - t_off
                                if not g_config.IS_DEPLOYED:
                                    print "power fail event duration = %f" % power_fail_event_duration
                                event_durations.append(power_fail_event_duration)
                                event_times.append(t_off)
                                if not g_config.IS_DEPLOYED:
                                    print "Found a %10.2f minute outage on %s" % (
                                        (power_fail_event_duration/60),
                                        arrow.get(t_off).format("MMMM DD, YYYY @ hh:mm A")
                                    )
                        else:
                            self.my_local_logger.info('Power event edges are mismatched, skipping this: ')
                    else:
                        self.my_local_logger.info('Power event edges in the window are mismatched, skipping this: ')
                else:
                    self.my_local_logger.info('Power event outage has low reliability, skipping this: ')

            self.my_local_logger.info('temporal data for cell has %d points from %s to %s' % (
                number_of_points, start_time, stop_time))
            cell['onts'][this_ont]['temporal_filter'] = {'reliability': reliability,
                                                         'event_durations': event_durations,
                                                         'event_times': event_times,
                                                         'time_domain_vector': time_domain_vector}

        return cell

    def spatial_filter(self, cell):
        """
        The spatial filter does a filtering of the ont collection based on the asset called this_asset.
        :param cell:
        A cell that contains of onts along with their locations and states.
        The onts values must have been filtered temporally first.

        :return:
        """
        if self.cell_time_event:
            # Only append outages on assets for the cells that have events
            if not g_config.IS_DEPLOYED:
                print "An interesting time event has occurred in this cell..."
            for this_ont in cell['onts']:
                event_durations = cell['onts'][this_ont]['temporal_filter']['event_durations']
                event_times = cell['onts'][this_ont]['temporal_filter']['event_times']
                if not g_config.IS_DEPLOYED:
                    if this_ont == "0016FE13":
                        print "found an event"
                for this_asset in cell['onts'][this_ont]['assets']:
                    if not g_config.IS_DEPLOYED:
                        if this_asset == "TR1000489404_108":
                            print "found a matching asset"
                    try:
                        event_activities = cell['assets'][this_asset]['spatial_filter']
                    except KeyError:
                        event_activities = {'distance': [], 'events': []}
                    if len(event_durations) > 0:
                        ont_lat = cell['onts'][this_ont]['lat_lon'][0]
                        ont_lon = cell['onts'][this_ont]['lat_lon'][1]
                        lat_lon = cell['assets'][this_asset]['lat_lon']
                        asset_lat = lat_lon[0]
                        asset_lon = lat_lon[1]
                        this_distance = lat_lon_distance(asset_lat, asset_lon, ont_lat, ont_lon,  units='mi')
                        event_activities['distance'].append(this_distance)
                        event_activities['events'].append(
                            {'event_durations': event_durations, 'event_times': event_times}
                        )
                    cell['assets'][this_asset]['spatial_filter'] = event_activities
            if not g_config.IS_DEPLOYED:
                print "  ...done with interesting cell."
        return cell

    def vote_on_assets(self, cell, temporal_data, spatial_data, voting_data):
        """
        :param cell:
        :param voting_data: an integer that is the number of votes to use
        :return:
        """
        try:
            this_filter = json.loads(spatial_data)
            total_counts = len(this_filter['r'])
            weights = []
            for i in range(total_counts):
                weights.append(this_filter['r'][i])
        except TypeError as e:
            self.my_local_logger.error('Spatial data has a Type Error: %s, %s' % (spatial_data, e))
        except ValueError as e:
            self.my_local_logger.error('Spatial data has a ValueError: %s, %s' % (spatial_data, e))

        self.my_local_logger.info('spatial data = %s', spatial_data)
        self.my_local_logger.info('temporal data = %s', temporal_data)
        if voting_data:
            try:
                number_of_votes = int(voting_data)
            except ValueError as e:
                self.my_local_logger.error('Voting data has en error in the passed value %s' % e)
                number_of_votes = 1
            except TypeError as e:
                self.my_local_logger.error('Voting data is not a string %s' % e)
                number_of_votes = 1
        else:
            number_of_votes = 1
        self.my_local_logger.info('Number of votes passed: %d' % number_of_votes)
        for this_asset in cell['assets']:
            cell['assets'][this_asset]['outage_events'] = None
            try:
                # these_distances = cell['assets'][this_asset]['spatial_filter']['distance']
                these_events = cell['assets'][this_asset]['spatial_filter']['events']
            except KeyError:
                # print "No outages on this asset"
                continue
            if len(these_events) > 0:
                if len(these_events) >= 1:  # number_of_votes:
                    # This is where the filter will take place.
                    # These events is an array.
                    # I must iterate over an array of these event items
                    try:
                        outage_events = cell['assets'][this_asset]['outage_events']
                    except KeyError:
                        outage_events = {'event_durations': [], 'event_times': []}
                    if outage_events is None:
                        outage_events = {'event_durations': [], 'event_times': []}
                    for this_event_dict in these_events:
                        for j, this_event in enumerate(this_event_dict['event_durations']):
                            outage_events['event_durations'].append(this_event)
                            outage_events['event_times'].append(this_event_dict['event_times'][j])
                    cell['assets'][this_asset]['outage_events'] = outage_events

        return cell

    def post_outage_on_asset(self, cell, payload):
        """
        :param cell:
        :param payload: this will be of the form

        http://10.123.0.27:8080/eon360/api/utilities?p=0&s=20

                "eonUtilityEntries": [
            {
              "id": "5508dacee4b0df5309df591e",
              "version": 0,
              #######################
              ##  ADD THIS GUID
              "guid": "46f7655c-9160-4c08-b272-59c32232ba9f",
              #######################
              "company": "CEDRAFT",
              "serviceAddress": "{\"CE Map ID\": \"None\",
                                  \"Municipality\": \"New Castle\",
                                  \"Provenance\":\"Report A\",
                                  \"Attached Assets\": [],
                                  \"Next Hop\": \"PS302355612\",
                                  \"Type\": \"HOUSE\",
                                  \"Downstream\": \"None\",
                                  \"Transformer Supply\": [\"TR302355616_T4\"],
                                  \"Upstream\":\"PS302355612\",
                                  \"Connections\": [],
                                  \"Address\":\"10 VALLEY VIEW RD, Chappaqua NY, 10514-2532\",
                                  \"Utility ID\": \"None\"}",
              "errorCode": "0",
              "circuitID": "10U2",
              "transformerID": "HS01c902165608e5f12ce4c01c78c70415",
              "eligibilityList": [
                {
                  "id": "54a079aae4b040db636a2d95",
                  "version": 0,
                  "guid": "23697667-4810-4169-8802-46ad6efae3a3",
                  "company": "",
                  "ontSerialNumber": "59054969",
                  "errorCode": "0.91",
                  "alarmID": "CHPQNYCPOL1*LET-3*11*1*1",
                  "ontAddress": "8 Brookside Cir,Chappaqua,NY,10514",
                  "modelCoefficients": null,
                  "longitude": f-73.787811,
                  "latitude": 41.175064,
                  "createdAtTimestamp": 1419803050366,
                  "lastModifiedAtTimestamp": 1419803050366
                },



                    "payload": {
                             "company": "CEDRAFT",
                             "outageTime": 1430452800000,
                             "longitude": lon,
                             "latitude": lat,
                             "circuitID": "",
                             "assetID": "",
                             "votes": 3,
                             "spatial": '{"r":[1,1]}',
                             "temporal": "[1,0; .8,24; .3, 60]",
                             "reputationEnabled": True,
                             "zoomT": 1,
                             "zoomR": 1,
                             "radius": 0.12,
                             "units": "MI"
                         },
                The post must be of the form
                        {
                          "eventDuration": "long",
                          "guid": "",
                          "id": "",
                          "utility": {
                            "assetType": "",
                            "circuitID": "",
                            "company": "",
                            "outageID": "",
                            "transformerID": ""
                          },
                          "timeOfEvent": "Date",
                          "company": "",
                          "longitude": 0,
                          "internalUtilityGuid": "",
                          "latitude": 0,
                          "algorithm": "",
                          "version": "long"
                        }
        :return:
        """
        # circuit_id = ""
        # First loop over all circuits:
        try:
            for this_circuit in cell['circuits']:
                # Now loop over all the items on that circuit
                for this_asset in cell['circuits'][this_circuit]['connected_items']:
                    asset_item = cell['assets'][this_asset]
                    outages = asset_item['outage_events']
                    # This is the form of an event (If there is one!)
                    # It will be None if there are no events otherwise it will be:
                    # 'event_durations': copy.deepcopy(these_events['event_durations']),
                    # 'event_times': copy.deepcopy(these_events['event_times'])
                    if outages:
                        self.my_local_logger.info('Examining circuit=%s, asset=%s. which has %d outages to post!' % (this_circuit, this_asset, len(outages)))
                        if this_asset[0:2] == "TR":
                            asset_type = "TRANSFORMER"
                        elif this_asset[0:2] == "HS":
                            asset_type = "HOUSE"
                        elif this_asset[0:2] == "PS":
                            asset_type = "POLE, SECONDARY"
                        elif this_asset[0:2] == "PP":
                            asset_type = "POLE, PRIMARY"
                        else:
                            asset_type = "OTHER"
                        for i, this_event_duration in enumerate(outages['event_durations']):
                            address_string = cell['assets'][this_asset]['serviceAddress']
                            self.my_local_logger.info("address_string = %s" % address_string)
                            address_string_pairs = json.loads(address_string)
                            this_address = ''
                            if "Municipality" in address_string_pairs.keys():
                                this_address += 'Municipality:' + address_string_pairs['Municipality'] + '|'
                            if "Address" in address_string_pairs.keys():
                                this_address += 'Address:' + address_string_pairs['Address'] + '|'
                            # Here's how to include the CE Map ID and the Utility ID if needed
                            # this_address += 'CE MapID:' + this_asset.split('_')[1] + '|'
                            # this_address += 'UtilityID:' + this_asset.split('_')[0][2:]
                            if this_address[-1] == '|':
                                this_address = this_address[:-1]
                            utility_document = {
                                "internalUtilityGuid": asset_item['guid'],
                                "eventDuration": int(round(this_event_duration * 1000)),
                                # "guid": "guid-here",
                                # "id": 'id-here',
                                "utility": {
                                    "assetType": asset_type,
                                    "circuitID": this_circuit,
                                    "company": payload["company"],
                                    "outageID": 'outage-id-here',
                                    "transformerID": this_asset,
                                    "address":  this_address
                                },
                                "timeOfEvent": int(round(outages['event_times'][i] * 1000)),
                                # "longitude": asset_item['lat_lon'][1],
                                # "latitude": asset_item['lat_lon'][0],
                                "algorithm": "NEAR10"
                                # "version": 0
                            }
                            if not g_config.IS_DEPLOYED:
                                print "Posting a %10.2f minute outage on %s, circuit: %s, asset_id: %s" % (
                                    (utility_document['eventDuration'] / 1000 / 60),
                                    arrow.get(utility_document['timeOfEvent'] / 1000).format("MMMM DD, YYYY @ hh:mm A"),
                                    utility_document['utility']['circuitID'],
                                    utility_document['utility']['transformerID']
                                )
                            self.my_local_logger.info('Posting: %s' % json.dumps(utility_document))
                            self.eon_api_bridge.groomed_outages_post_20(utility_document)
                    else:
                        if not g_config.IS_DEPLOYED:
                            print "Nothing to post for circuit: %s, asset_id: %s" % (
                                this_circuit,
                                this_asset
                        )
        except:
            self.my_local_logger.error('Posting outage error')

    def build_in_memory_cell_db(self, cell):
        """
        :param cell: A cell of data that represents the collection of onts, assets and circuits along with the alarms
        Creates an in-memory data structure that has this information:
            this_cell = {'neighbors': [],  # the 6 nearest neighbors
                    'assets': {}, # The utility assets including their lat and lon and events
                    'onts': {}, # Verizon's ONTs including their lat and lon and events
                    'state': '' # A string representing the state of this cell.
                                    This is used for multi threading purposes so that neighboring cells can see
                                    whats going on.
                    'circuits': {} # This is a set of circuits in this cell. All assets on a circuit
                                     are in the circuits list
                    'lat_lon': [] # The lat and lon array of the center of the cell
                    'radius': 1.00 # The radius of the circumscribed cell.
            ont_items is a dictionary of {'lat_lon':[],'assets':[],'events':[]}
            asset_items is a dictionary of {'lat_lon':[],'onts':[],'events':[]}
        :return: none
        """
        asset_dict = {'groom_time': cell['groom_time']}
        for this_asset in cell['assets']:
            asset_dict[this_asset] = SortedDict()
            for this_ont in cell['assets'][this_asset]['onts']:
                this_distance = lat_lon_distance(cell['assets'][this_asset]['lat_lon'][0],
                                                 cell['assets'][this_asset]['lat_lon'][1],
                                                 cell['onts'][this_ont]['lat_lon'][0],
                                                 cell['onts'][this_ont]['lat_lon'][1])

                for this_event in cell['onts'][this_ont]['events'][0]:
                    event_key = int(this_event / 1000)
                    if event_key in asset_dict[this_asset]:
                        asset_dict[this_asset][event_key]['voters'].update({this_distance: this_ont})
                    else:
                        voters = SortedDict()
                        voters.update({this_distance: this_ont})
                        asset_dict[this_asset].update({event_key: {'state': 0, 'voters': voters}})
                        # self.my_local_logger.debug("%d,0,%s,%s,%f" % (event_key, this_ont, this_asset, this_distance)

                for this_event in cell['onts'][this_ont]['events'][1]:
                    event_key = int(this_event / 1000)
                    if event_key in asset_dict[this_asset]:
                        asset_dict[this_asset][event_key]['voters'].update({this_distance: this_ont})
                    else:
                        voters = SortedDict()
                        voters.update({this_distance: this_ont})
                        asset_dict[this_asset].update({event_key: {'state': 1, 'voters': voters}})
                        # self.my_local_logger.debug("%d,1,%s,%s,%f" % (event_key, this_ont, this_asset, this_distance)

        self.asset_dictionary = asset_dict
        self.my_local_logger.debug("done with build_in_memory_cell_db")

    @staticmethod
    def compute_cell_guid(payload, resolution):
        """
        Computes a GUID based on the lat lon and time value
        """
        # query_guid = payload["query_guid"]
        this_lat = payload["latitude"]
        this_lon = payload["longitude"]
        # utility = payload["company"]
        outage_test_time = payload["outageTime"]
        # circuit_id = payload["circuitID"]
        # asset_id = payload["assetID"]
        # votes = payload["votes"]
        # spatial = payload["spatial"]
        # temporal = payload["temporal"]
        # reputation_ena = payload["reputationEnabled"]
        # zoom_t = payload["zoomT"]
        # zoom_r = payload["zoomR"]
        # radius = payload["radius"]
        # units = payload["units"]
        # The number of decimal points in the lat and lon gridify the guid
        fmt_str = "%%4.%df_%%4.%df_%%d" % (resolution, resolution)
        this_guid = fmt_str % (this_lat, this_lon, outage_test_time)
        cell_guid = this_guid.replace(".", "p").replace("-", "m")
        timestamp_guid = "%d" % outage_test_time
        return cell_guid, timestamp_guid

    def save_cell_in_shared_mem(self, this_cell_guid, cell):
        while not self.shared_data_lock.acquire(False):
            self.my_local_logger.info('Waiting to acquire lock for shared data.')
            time.sleep(g_config.SLEEP_TIME)
        self.shared_data['cell_collection_set'].add(this_cell_guid)
        self.shared_data['cell_collection_dict'][this_cell_guid] = cell
        self.shared_data_lock.release()

    def get_shared_data(self, query_type="all", dict_key=None):
        my_shared_data = None
        if query_type == "all":
            while not self.shared_data_lock.acquire(False):
                self.my_local_logger.info('groom_outages: waiting to acquire lock for shared data.')
                time.sleep(g_config.SLEEP_TIME)
            my_shared_data = copy.copy(self.shared_data)
            self.shared_data_lock.release()
        elif query_type == "cell_collection_dict":
            while not self.shared_data_lock.acquire(False):
                self.my_local_logger.info('groom_outages: waiting to acquire lock for shared data.')
                time.sleep(g_config.SLEEP_TIME)
            if dict_key is not None:
                my_shared_data = copy.copy(self.shared_data['cell_collection_dict'][dict_key])
            else:
                my_shared_data = copy.copy(self.shared_data['cell_collection_dict'])
            self.shared_data_lock.release()
        elif query_type == "cell_collection_dict_keys":
            while not self.shared_data_lock.acquire(False):
                self.my_local_logger.info('groom_outages: waiting to acquire lock for shared data.')
                time.sleep(g_config.SLEEP_TIME)
            my_shared_data = copy.copy(self.shared_data['cell_collection_dict'].keys())
            self.shared_data_lock.release()
        elif query_type == "cell_collection_set":
            while not self.shared_data_lock.acquire(False):
                self.my_local_logger.info('groom_outages: waiting to acquire lock for shared data.')
                time.sleep(g_config.SLEEP_TIME)
            my_shared_data = copy.copy(self.shared_data['cell_collection_set'])
            self.shared_data_lock.release()

        return my_shared_data

    def build_new_cell(self, this_cell_guid, this_items_payload, ttl):
        """
        Builds a cell and stores it in local shared memory
        """
        self.my_local_logger.debug("BUILDING_CELL %d, %s" % (self.cell_count, this_cell_guid))
        t0 = time.time()
        # Step 3) Query the API and find all utility assets within the region of interest
        cell = self.get_data_in_cell_area(this_items_payload, ttl)  # lat, lon, radius, this_time, ttl)
        t1 = time.time()
        self.my_local_logger.debug("API calls to get %d assets in a %f %s radius took %f seconds" %
                                   (len(cell['assets']), cell['radius'], g_config.RADIUS_UNITS, (t1 - t0)))
        self.persist_cell_pickle(cell, this_cell_guid)
        self.my_local_logger.debug("Saved the cell pickle")
        t0 = time.time()
        self.build_in_memory_cell_db(cell)
        t1 = time.time()
        self.my_local_logger.debug("Building in memory data took %f seconds" % (t1 - t0))
        # plot_assets(self.asset_dictionary)
        # Step 4) Save this cell to the shared memory set

        self.cell_count += 1
        return cell

    def mark_cell_in_shared_memory(self, cell_guid):
        self.my_local_logger.debug("MARKING_CELL %s" % cell_guid)
        while not self.shared_data_lock.acquire(False):
            self.my_local_logger.info('Waiting to acquire lock for shared data.')
            time.sleep(g_config.SLEEP_TIME)
        self.shared_data['cell_collection_set'].add(cell_guid)
        self.shared_data_lock.release()

    def queue_to_publish(self, message):
        while not self.outgoing_queue_lock.acquire(False):
            self.my_local_logger.info('Groomer is waiting to acquire lock on publisher queue.')
            time.sleep(g_config.SLEEP_TIME)
        self.my_local_logger.debug("Groomer got consumer_queue_lock, ")
        self.outgoing_q.put(message, False)
        self.my_local_logger.debug("        after putting message in queue size is now: %d" % self.outgoing_q.qsize())
        if self.outgoing_queue_lock:
            self.outgoing_queue_lock.release()
            self.my_local_logger.debug(
                "Groomer released the consumer_queue_lock. Queue size is now:%d" % self.outgoing_q.qsize())
            self.my_local_logger.info('Publish message queued, lock released.')

    def groom_outages(self):
        """
        This method grooms the outages by looking at the internal shared queue and pulling off the items that are
        ready to be processed. The shared queue is passed between processes contains the cell data along with
        processing state for each cell.
        """
        #######################################################
        # This is the general flow for the groom process
        # When the queue is hit then it will have the start and end times along with the various parameters
        # needed for the outage event calculation.
        # When the queue item comes in then these steps happen.
        #
        #    h) temporal filter : a string that represents time domain filter coefficients.
        #       The string will be of this form:
        #        "[1,0; .8,24; .3, 60]"
        #        "[w0,t0; w1,t1; w2, t2; ...]"  were w0 is the weight (typically between 0 and 1)
        #                                       and t0 is the historical time
        #         (in minutes) from the event.  In this example the following rules are used:
        #              At the event time, the alarm will be weighted with 1, 24 minutes before the event the alarm
        #              will be weighted by .8, 60 minutes before the event the alarm will be weighted by 0.3.
        #              For events that happen between the time weights a linear interpolation will be used.
        #    i) use reputation (flag) : a flag that says whether to use the reputation of the ONTs for voting
        self.start_time = time.time()
        self.my_local_logger.debug("GROOMING NOW")
        # lat = 41.2693778
        # lon = -73.8773389
        # radius = 1.0  # config.START_RADIUS  # = 0.12
        # #################################################
        # STEP 1 Pull items off the queue.
        #  self.pull_q_groom_command()
        self.groomer_state = "1:GROOM"
        groom_queue_len = len(self.local_q)
        if groom_queue_len == 0:
            self.my_local_logger.debug("NOTHING IN LOCAL QUEUE, returning")
            self.groomer_state = "1.0:GROOM_RETURN_EARLY"
            return
        self.my_local_logger.debug("------------------ processing all %d items in the local_q" % groom_queue_len)
        for _ in range(groom_queue_len):
            # STEP 1) Pull items off the queue. The queue will consist of:
            # a) time : in in microseconds that is desired for calculating the outage
            #    b) lat : latitude in decimal degrees
            #    c) lon : longitude in decimal degrees
            #    d) circuitID : circuit ID filter to be used for identification of a
            #       specific circuit within the area of interest
            #    e) assetID : asset ID filter to be used within the area of interest
            #    f) number of votes : number of votes to be used for qualifying the outage
            #    g) spatial filter : a string that represents radial filter coefficients. This is a string of the form:
            #        "[1,0; .2,.2; .3,.01]"
            #        "[w0,d0; w1,d1; w3,d3; ... ]"  where w0 is the weight (typically 0 to 1)
            #                                       and d0 is the distance in miles or
            # whatever the units are set to in the config file.
            # The distance is the distance along a line that runs through the asset lat/lon and is parallel to the
            # nearest upstream circuit segment.  The ONT distance is projected to this circuit line and is filtered
            # by the same spatial filter coefficients.
            # In addition to the spatial filter the ONTs are weighted by their reputation
            #    (if the flag is set) which is
            # calculated by an internally learned algorithm.
            self.my_local_logger.debug(" Grooming local_q, size = %d" % len(self.local_q))
            top_of_q_data = copy.copy(self.local_q.popleft())  # was popleft
            self.groomer_state = "1.1:GROOM_POP_QUEUE"
            self.my_local_logger.info("Got a local queue item.")
            if "ttl" in top_of_q_data.keys():
                ttl = top_of_q_data["ttl"]
            else:
                ttl = self.ttl
            if top_of_q_data["payload"]['radius'] != self.working_radius:
                self.resolution = compute_resolution(top_of_q_data["payload"]["radius"])
            this_cell_guid, this_timestamp_guid = self.compute_cell_guid(top_of_q_data["payload"], self.resolution)
            keys = self.get_shared_data('cell_collection_dict_keys')
            collection_set = self.get_shared_data('cell_collection_set')
            ##################################################
            # STEP 2) Look at the GUID generator for the lat and lon and see if the shared
            # memory contains a cell structure for this item.
            if this_cell_guid in keys:  # my_shared_data['cell_collection_dict'].keys():
                # 2.1) If it does contain the GUID then determine the state of that cell.
                # 2.2) If the time stamp GUID of this cell GUID is within the resolution outage
                #      machine then continue with step 4.
                self.groomer_state = "1.2:GROOM_FOUND_SHARED_DATA"
                self.my_local_logger.debug("This cell is already in shared memory, "
                                           "and is fully populated checking using a copy of it")
                cell = self.get_shared_data('cell_collection_dict', this_cell_guid)
                self.my_local_logger.debug("EXISTS: %s[%f,%f]TTL=%d" %
                                           (this_cell_guid, cell["lat_lon"][0], cell["lat_lon"][1], cell["ttl"]))
            else:  # 2.3) If it does not contain the GUID or the time stamp GUID does not match then go to step 3.
                # STEP 3) Query the API and find all utility assets within the region of interest
                # (defined by a config parameter as the starting zoom level in miles)
                # These will include house, transformers, poles, wires and so on.
                # The first 2 letters of the assetID will be the item type. Save this cell to the shared memory set
                # From this collection of assets create a SET of items in a shared queue that
                # holds these items until so that other processes don't work on these items at the same time.
                # The items will be filtered by assetID (item 1e) and circuitID (item 1d) if these fields are filled in.
                cell = self.build_new_cell(this_cell_guid, top_of_q_data["payload"], ttl)
                self.save_cell_in_shared_mem(this_cell_guid, cell)
                self.my_local_logger.debug("CREATE: %s[%f,%f]TTL=%d" %
                                           (this_cell_guid, cell["lat_lon"][0], cell["lat_lon"][1], ttl))
                self.groomer_state = "1.3:GROOM_BUILD_NEW_CELLS"

            # self.plot_assets()

            # At this point the cell has been created and tested to be sure that its the one we want.
            # Now examine the neighboring cells from this cells collection:

            # STEP 4) Using the result of step 3 the cell is ready to be processed.
            #  4.1) The next step is to look at each of the 6 neighboring cells.
            #  This is done by examining the 6 cells and determining their state.
            #    4.1.1) Check the TTL count of this cell. If the TTL is zero continue to the next cell
            #           in the incoming Queue.
            self.groomer_state = "1.4:GROOM_PROPAGATE_CELL"

            if cell['ttl'] != 0:
                for i, items in enumerate(cell['neighbors']):  # the 6 nearest neighbors
                    this_neighbor_cell = items[0]
                    angle = items[1]
                    #  The six neighbor cells are initially set to zero
                    #   this_cell = {'neighbors': [["",0], ["",60], ["",120], ["",180], ["",240],["",300]],
                    #                'assets': {},
                    #                'onts': {},
                    #                'circuits': {},
                    #                'state': 'create',
                    #                'lat_lon': [lat, lon],
                    #                'radius': radius,
                    #                'groom_time': groom_time
                    #                }
                    distance = 2 * top_of_q_data["payload"]["radius"]
                    if not this_neighbor_cell:
                        # We need to copy each of the neighbor cells to make sure we get a unique data structure
                        neighbor_cell_message = copy.copy(top_of_q_data)
                        self.my_local_logger.debug("%s neighbor[%d] is empty, [%f][%f], filling it now" %
                                                   (this_cell_guid, i, cell["lat_lon"][0], cell["lat_lon"][1]))
                        new_lat, new_lon = move_to_lat_lon(cell["lat_lon"][0], cell["lat_lon"][1], distance, angle)
                        # jump out of the loop if the cell is outside the region of interest
                        company_name = top_of_q_data['payload']['company']
                        if company_name not in self.utility_region.keys():
                            self.my_local_logger.error("Skipping cell rebroadcast "
                                                       "because company_name='%s' is not in utility_region." %
                                                       company_name)
                            self.groomer_state = "1.5.0:GROOM_ABORT_PROPAGATE"
                            continue

                        if (new_lat < self.utility_region[company_name]['min_latitude']) or \
                                (new_lat > self.utility_region[company_name]['max_latitude']) or \
                                (new_lon > self.utility_region[company_name]['max_longitude']) or \
                                (new_lon < self.utility_region[company_name]['min_longitude']):
                            # Here is where the outage time can be advanced by 2 weeks and run again.
                            if not g_config.IS_DEPLOYED:
                                print "Skipping neighbor cell rebroadcast at " \
                                      "lat = %f, lon = %f because outside utility region." % \
                                      (new_lat, new_lon)
                            self.my_local_logger.info("Skipping neighbor cell rebroadcast at "
                                                      "lat = %f, lon = %f because outside utility region." %
                                                      (new_lat, new_lon))
                            self.groomer_state = "1.5.1:GROOM_ABORT_PROPAGATE"
                            continue
                        neighbor_cell_message["payload"]["longitude"] = new_lon
                        neighbor_cell_message["payload"]["latitude"] = new_lat
                        new_cell_guid, new_timestamp_guid = self.compute_cell_guid(neighbor_cell_message["payload"],
                                                                                   self.resolution)
                        if new_cell_guid not in collection_set:
                            # STEP 5) Queue up a grooming process for neighboring cells that
                            # allows another process to pick up the outage calculation for the rest of the circuit.
                            # The neighboring cell is defined by outage location +/- 1 one patch area of
                            # interest in 6 hexagonal directions. This will create a small overlap on the cell corners.
                            self.groomer_state = "1.5.1:GROOM_QUEUE_NEIGHBOR"
                            self.my_local_logger.debug("queue length X = %d" % len(self.local_q))
                            self.mark_cell_in_shared_memory(new_cell_guid)
                            if cell['ttl'] == -1:
                                # If the TTL count is -1 then this is a full propagation list so this causes a
                                # post (publish) of a new query. Then continue with the next cell.
                                neighbor_cell_message["ttl"] = -1
                            else:
                                # Decrease the TTL count and post (publish) a new query.
                                # Then continue with the next cell.
                                neighbor_cell_message["ttl"] = cell['ttl'] - 1
                            self.my_local_logger.debug("  POST: %s[%f,%f]TTL=%d->%s[%f,%f]TTL=%d(%d)" %
                                                       (this_cell_guid, cell["lat_lon"][0], cell["lat_lon"][1], ttl,
                                                        new_cell_guid, new_lat, new_lon, neighbor_cell_message["ttl"],
                                                        angle))
                            ########################
                            # This is the work around to just post the message back to the local_q instead of sending it
                            # out to the rabbit bus for parallel processing
                            ####################################
                            #  BURNED BY PYTHON
                            ####################################
                            # The queue append does not copy the data, instead it just posts a pointer to the data
                            # self.local_q.append(copy.deepcopy(neighbor_cell_message))
                            # self.my_local_logger.debug("gueue length Y = %d" % len(self.local_q)
                            self.queue_to_publish(copy.deepcopy(neighbor_cell_message))
                        else:
                            self.groomer_state = "1.5.2:GROOM_LINK_NEIGHBOR"
                            # time.sleep(1)
                            self.my_local_logger.debug("Stitching %s's neighbor[%d]@[%f][%f] to this cell: %s" %
                                                       (this_cell_guid, i, cell["lat_lon"][0], cell["lat_lon"][1],
                                                        new_cell_guid))
                            self.my_local_logger.debug("SHARED: %s[%f,%f]TTL=%d->%s[%f,%f]TTL=%d (%d)" %
                                                       (this_cell_guid, cell["lat_lon"][0], cell["lat_lon"][1], ttl,
                                                        new_cell_guid, new_lat, new_lon, cell['ttl'], angle))
                            # If the cell is already in shared memory then just connect the cells neighbors
                            cell['neighbors'][i] = [new_cell_guid, angle]
                self.save_cell_in_shared_mem(this_cell_guid, cell)

            # STEP 6) OUTAGE CALCULATION
            # at this point the outage region is contained within one cell.
            # This is the process of grooming the outage. The data is ready to be used for calculating the outage.
            # The filter algorithm was given above.
            # 6.1) First the temporal filter is applied to the assets in the cell
            self.groomer_state = "1.6:GROOM_COMPUTE_OUTAGE"
            t_cell = self.temporal_filter(cell)
            self.save_cell_in_shared_mem(this_cell_guid, t_cell)
            # 6.2) Second the spatial filter is applied to each assets in the cell
            s_cell = self.spatial_filter(t_cell)
            self.save_cell_in_shared_mem(this_cell_guid, s_cell)
            # 6.3) Once the filtered data is ready then the vote is applied to each ONT and the final vote is computed.
            v_cell = self.vote_on_assets(s_cell,
                                         top_of_q_data['payload']['temporal'],
                                         top_of_q_data['payload']['spatial'],
                                         top_of_q_data['payload']['votes'])
            self.save_cell_in_shared_mem(this_cell_guid, v_cell)
            #      and the results is written back to the outage API.
            self.my_local_logger.info("Calling post_outage_on_asset.")
            self.my_local_logger.info("Posting this payload: %s" % json.dumps(top_of_q_data["payload"]))
            self.post_outage_on_asset(v_cell, top_of_q_data["payload"])

        self.end_time = time.time()
        elapsed_process_time = fmax(self.end_time - self.start_time, .001)
        self.groomer_state = "0:IDLE"
        self.groom_run_state = "0:IDLE"
        self.my_local_logger.info("Done. Elapsed time %f sec." % elapsed_process_time)

    @staticmethod
    def build_groom_payload(this_date, company=None, trigger_time=0, lat=0, lon=0, ttl=0):
        """
        :param this_date: The date that the groom operation is to be examined
        :param company: The utility company name associated with this alarm (if any)
        :param trigger_time: The time of the alarm.
        :param lat: Latitude of the alarm
        :param lon: Longitude of the alarm
        :param ttl: Time to live (set to 2 to limit the range of area to examine)
        :return:  The payload for the groom queue (or None if there is no utility)
        Note that the first company is returned. There may be cases where the utilities may overlap. There are better
        test methods for determining whether a point is in a region or not.
        """
        this_payload = None
        if company is None:
            for this_company in g_config.UTILITY_REGION:
                #:TODO: Replace with a better test method. See http://alienryderflex.com/polygon/
                if g_config.UTILITY_REGION[this_company]['min_latitude'] < lat < \
                                g_config.UTILITY_REGION[this_company]['max_latitude'] and \
                                g_config.UTILITY_REGION[this_company]['min_longitude'] < lon < \
                                g_config.UTILITY_REGION[this_company]['max_longitude']:
                    company = this_company
                    break
        if company is not None:
            this_payload = {"dateTime": this_date,
                            "payload": {"company": company,
                                        "outageTime": trigger_time,
                                        "longitude": lon,
                                        "latitude": lat,
                                        "circuitID": "",
                                        "assetID": "",
                                        "votes": 0,
                                        "spatial": '{"r":[1,1]}',
                                        "temporal": "[1,0; .8,24; .3, 60]",
                                        "reputationEnabled": True,
                                        "zoomT": 1,
                                        "zoomR": 1,
                                        "radius": 0.12,
                                        "units": "MI"
                                        },
                            "messageType": "Save",
                            "ttl": ttl
                            }
        return this_payload

    @staticmethod
    def build_payload(this_date, this_company, this_trigger_time, this_lat, this_lon, ttl):
        this_payload = {"dateTime": this_date,
                        "payload": {"company": this_company,
                                    "outageTime": this_trigger_time,
                                    "longitude": this_lon,
                                    "latitude": this_lat,
                                    "circuitID": "",
                                    "assetID": "",
                                    "votes": 0,
                                    "spatial": '{"r":[1,1]}',
                                    "temporal": "[1,0; .8,24; .3, 60]",
                                    "reputationEnabled": True,
                                    "zoomT": 1,
                                    "zoomR": 1,
                                    "radius": 0.12,
                                    "units": "MI"
                                    },
                        "messageType": "Save",
                        "ttl": ttl
                        }
        return this_payload

    def utility_groom(self, utility_name="ALL", location=None, ttl=g_config.TTL_MAX):
        """
        Triggers a Utility wide grooming process by setting up a ttl of -1 and injecting it into the Rabbit MQ bus.
        When called, the outage test location is calculated by starting in the center of the geographic location
        using the current time for outage detection.
        All utilities in the utility dictionary will be groomed when this method is called.

        :param: utility_name: the utility to groom or ALL for all
        :param: location: is the groom location which will be the starting point of the groom process. If the value is
                passed in and is not none then the groom will occur within a TTL_MAX region of this location
        :return:
        """
        # TODO: The best approach here is to trigger the outage groom at the center of the last alarm.
        # trigger_time = arrow.get("2015-01-09T19:42:33.689-0400").timestamp*1000
        trigger_date = arrow.utcnow().to('US/Eastern').format('YYYY-MM-DDTHH:mm:ss.SSSZ')
        trigger_time = arrow.get(trigger_date).timestamp*1000
        if location is None:
            ttl = g_config.TTL_RANDOM_GROOM
            if utility_name in self.utility_region.keys():
                r = random.random()
                this_lat = r * (self.utility_region[utility_name]['max_latitude'] -
                                self.utility_region[utility_name]['min_latitude']) + \
                                self.utility_region[utility_name]['min_latitude']
                r = random.random()
                this_lon = r * (self.utility_region[utility_name]['max_longitude'] -
                                self.utility_region[utility_name]['min_longitude']) + \
                           self.utility_region[utility_name]['min_longitude']
                this_payload = self.build_groom_payload(trigger_date, utility_name, trigger_time, this_lat, this_lon, ttl)
                self.my_local_logger.info("SEEDED %s" % this_payload)
                if this_payload is not None:
                    self.queue_to_publish(this_payload)
            else:
                for company in self.utility_region.keys():
                    r = random.random()
                    this_lat = r * (self.utility_region[company]['max_latitude'] -
                                    self.utility_region[company]['min_latitude']) + \
                               self.utility_region[company]['min_latitude']
                    r = random.random()
                    this_lon = r * (self.utility_region[company]['max_longitude'] -
                                    self.utility_region[company]['min_longitude']) + \
                       self.utility_region[company]['min_longitude']
                    this_payload = self.build_groom_payload(trigger_date, company, trigger_time, this_lat, this_lon, ttl)
                    self.my_local_logger.info("SEEDED %s" % this_payload)
                    if this_payload is not None:
                        self.queue_to_publish(this_payload)
        else:
            if utility_name in self.utility_region.keys():
                this_lat = location["lat"]
                this_lon = location["lon"]
                this_payload = self.build_groom_payload(trigger_date, utility_name, trigger_time, this_lat, this_lon,
                                                  ttl)
                self.my_local_logger.info("SEEDED %s" % this_payload)
                if this_payload is not None:
                    self.queue_to_publish(this_payload)
            else:
                for company in self.utility_region.keys():
                    this_lat = location["lat"]
                    this_lon = location["lon"]
                    this_payload = self.build_groom_payload(trigger_date, company, trigger_time, this_lat, this_lon,
                                                      ttl)
                    self.my_local_logger.info("SEEDED %s" % this_payload)
                    if this_payload is not None:
                        self.queue_to_publish(this_payload)

    def run(self):
        # self.my_local_logger.push
        self.run_start_time = time.time()
        report_time = self.run_start_time + g_config.KEEP_ALIVE_INTERVAL
        self.my_local_logger.debug("Started at %f" % self.run_start_time)  # "backend_msg_handler.run")
        while self.run_enable:
            # Also add a timeout so that if the queue isn't full it processes alarms anyway.
            elapsed_time = time.time() - self.run_start_time
            if time.time() > report_time:
                self.my_local_logger.info("|OK dT|%10.3f|(s)|%10.3f|e|%10.3f|elp|%10.3f|state|%s|groomer state|%s" %
                                          (self.end_time - self.start_time,
                                           self.start_time,
                                           self.end_time,
                                           elapsed_time,
                                           self.groom_run_state,
                                           self.groomer_state)
                                          )
                report_time = time.time() + g_config.KEEP_ALIVE_INTERVAL
                self.idle_count += 1
                self.groom_run_state = "1:REPORT"

            queue_depth = len(self.local_q)
            groom_now = False
            if queue_depth > g_config.QUEUE_SIZE_BLOCK:
                groom_now = True
                self.my_local_logger.info("Analyzing after %f sec because queue size is %d" %
                                          (elapsed_time, queue_depth))  # , "backend_msg_handler.run")
            elif queue_depth > 0 and (elapsed_time > g_config.MESSAGE_EXPIRATION_SEC):

                groom_now = True
                self.my_local_logger.info("Analyzing after %f sec because time expired." %
                                          elapsed_time)  # , "backend_msg_handler.run")
            # when the backend message queue is QUEUE_SIZE_BLOCK then block this thread and process the queue
            if groom_now:
                self.groom_run_state = "2:GROOMING"
                self.groom_outages()
            # need to acquire a lock when pulling from the queue
            if not self.incoming_rabbit_mq.empty():
                self.idle_count = 0
                self.my_local_logger.debug("Message received, calling the process_incoming_queue now: %f" %
                                           elapsed_time)
                self.groom_run_state = "3:PROCESS_QUEUE"
                self.process_incoming_rabbit_mq()
                # set the run_start_time to begin timing at the time that the last message was queued
                self.run_start_time = time.time()

    def join(self, timeout=None):
        self.run_enable = False
        self.my_local_logger.info("Stopping at %f" % (time.time()))


if __name__ == "__main__":
    from g_pika_rabbit_bridge import MqConsumer, MqPublisher
    import logging.handlers
    import datetime

    BASE_DIR = 'C:\\repo\\personal\\myDocs\\Aptect\\Verizon\\Workproduct\\EON-IOT\\groomer'
    LOG_FORMAT = '%(asctime)s %(name)-12s %(levelname)-8s %(funcName)s %(lineno)5d :%(message)s'
    ########################
    # LOG FILE SETUP
    ########################
    unique_str = datetime.datetime.now().isoformat().replace(':', '_').replace('.', '_').replace('-', '_')

    try:
        os.mkdir(BASE_DIR + os.sep + g_config.LOG_DIR)
    except OSError or WindowsError:
        print "Log directory exists"

    try:
        os.mkdir(BASE_DIR + os.sep + g_config.PICKLES)
    except OSError or WindowsError:
        print "Pickles directory exists"

    LOG_FILENAME = BASE_DIR + os.sep + g_config.LOG_DIR + os.sep + 'top_' + unique_str + '.log'
    # Add the log message handler to the logger
    handler = logging.handlers.RotatingFileHandler(LOG_FILENAME, maxBytes=5000000, backupCount=50)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt='%m-%d %H:%M:%S'))
    handler.setLevel(logging.DEBUG)
    # Add this handler to the root logger
    logging.getLogger('').addHandler(handler)

    shared_data_top = {'thread_name_pool': set(),  # This contains a set of thread names that are sharing this data
                       'master_ont_set': set(),  # This contains all the ONTs that have been seen for this groom cycle
                       'master_ont_dict': {},  # This contains the dictionary of ONTs that have been seen
                       "cell_collection_set": set(),  # This contains all the cell guids that have been seen so far
                       "cell_collection_dict": {}}  # This is a dictionary of the cell quids that have been seen
    # and have been filled in with cell data
    shared_data_lock_top = threading.Lock()

    rabbit_message_queue = Queue.Queue()
    rabbit_queue_lock = threading.Lock()

    # EON_MQ_IP = '10.123.0.20'
    EON_MQ_IP = 'localhost'
    EON_MQ_UN = 'manager'  # 'manager'  #
    EON_MQ_PW = 'e0n36o'  # 'manager'  #
    EON_MQ_PORT = 5672
    EON_MQ_BASE = '/#/queues'
    EON_MQ_VHOST = 'eon360'
    EON_MQ_QUEUE = 'collection-notification'
    EON_GROOM_QUEUE = 'grooming-notification'
    connection_string = 'amqp://' + EON_MQ_UN + ':' + EON_MQ_PW + '@' + EON_MQ_IP + ':' + \
                        ('%d' % EON_MQ_PORT) + '/' + EON_MQ_VHOST

    consumer = MqConsumer(connection_string, rabbit_message_queue, rabbit_queue_lock, EON_GROOM_QUEUE)

    # # Can probably use the next line to look for a failed pika bridge.
    # It will be None if the connection is not available.
    # consumer.__dict__['_connection']

    publish_message_queue = Queue.Queue()
    publish_queue_lock = threading.Lock()
    publisher = MqPublisher(connection_string, publish_message_queue, publish_queue_lock, EON_GROOM_QUEUE)

    groomer = GroomingMessageHandler(incoming_q=rabbit_message_queue,
                                     incoming_queue_lock=rabbit_queue_lock,
                                     outgoing_q=publish_message_queue,
                                     outgoing_queue_lock=publish_queue_lock,
                                     module_instance_name='Handler01',
                                     shared_data=shared_data_top,
                                     shared_data_lock=shared_data_lock_top)

    groomer.run_enable = True

    groomer.start()
    consumer.start()
    publisher.start()

    run_mode = True
    try:
        #  This is Corlandt NY
        # This is what a groom payload should look like:
        # The spec version 1.1 shows this format
        # {
        #     “queryGuid": "dffdd6e5-79df-4da7-9a6d-84a8d3ead772",   A unique ID that is created
        #                                                      when the query button is clicked.
        #     “type”: "Query",                                Message type that is to be processed
        #     Type	of Action can be one of:
        #          Save:	    Save button clicked on the GUI
        #          Test:	    Query button clicked when the mode selection is Test
        #          Query:	    Query button clicked when the mode selection is Query (default)
        #          Clear:	    User browses away from page
        #
        #     "payload": {                                   The payload of the data from the web page form
        #         "company": "CEDRAFT",                      The company name being used on this web page
        #         "outageTime": 1414011303715,               The datetime from the web page form
        #         "latitude": 41.07597,                      Latitude (optional)
        #         "longitude": -74.011081,                   Longitude (optional)
        #         "circuitID",: "",                          Circuit ID (optional), as known by the utility
        #         "assetID": "",                             Asset ID (optional), as known by the utility (transformer)
        #         "votes": 3,                                Votes (optional) to use for outage 1 to 10
        #         "spatial": "[1,0; .2,.2; .3,.01]",         A spatial vector string (optional) consisting of weight,
        #                                                       distance pairs
        #         "temporal":"[1,0; .8,24; .3, 60]",         A temporal vector string (optional) consisting of weight,
        #                                                       time pairs
        #         "reputationEnabled": true,                 The state of the reputation check box. If checked then
        #                                                        this value is true otherwise false
        #         "zoomT": 1,                                The current zoom level of the time in the display plot
        #         "zoomR": 1,                                The current zoom level of the radius in the display plot
        #         “radius”: 1	                             The radius to use for the starting zoom level
        #         “units” : "MI"	                             The units of the radius. (MI or KM)
        #     }
        # }
        # This will be the outage time of the test (January 9th, 2015)

        # The types of messages implemented are Query, Save

        lat = 41.2693778
        lon = -73.8773389
        radius = 1.0  # config.START_RADIUS  # = 0.12

        outage_time = arrow.get("2015-01-09T19:42:33.689-0400").timestamp*1000
        today = arrow.utcnow().to('US/Eastern').format('YYYY-MM-DDTHH:mm:ss.SSSZ')
        groom_payload = {"queryGuid": "4a1b34bc-9739-4b40-85e1-8f464fe98211",
                         "dateTime": today,
                         "payload": {
                             "company": "CEDRAFT",
                             "outageTime": outage_time,
                             "longitude": lon,
                             "latitude": lat,
                             "circuitID": "",
                             "assetID": "",
                             "votes": 3,
                             "spatial": '{"r":[1,1]}',
                             "temporal": "[1,0; .8,24; .3, 60]",
                             "reputationEnabled": True,
                             "zoomT": 1,
                             "zoomR": 1,
                             "radius": 0.12,
                             "units": "MI"
                         },
                         "messageType": "Save"
                         }
        publisher.message = groom_payload
        while True:
            pass

        groomer.join()
        consumer.join()
        publisher.join()

    except KeyboardInterrupt:
        groomer.join()
        # consumer.join()
