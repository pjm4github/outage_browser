#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) 2014 Patrick Moran for Verizon
#
# Distributes WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License. If not, see <http://www.gnu.org/licenses/>.
import g_config as config
import json
import logging
import requests
import os


class EonApiBridge:
    ON = 1
    OFF = 0

    def __init__(self):
        """
        These are the interfaces to the EON API as defined in the SWAGGER document.
        """
        self.my_local_logger = logging.getLogger(__name__)
        self.my_local_logger.setLevel(logging.INFO)

        self.HEADERS = {'Content-type': 'application/json', 'Accept': 'text/plain'}
        # This will be  http://10.122.116.17:28080/eon360/api/
        self.API_BASE = "http://" + config.EON_INGESTOR_API_IP + ":" + ("%d" % config.EON_INGESTOR_API_PORT)\
                        + config.EON_INGESTOR_API_BASE
        self.session = requests.Session()
        self.status = ''
        self.base_timeout = 45.0
    ##################################################################
    # ALARMS : PONS-NMS alarm related operations
    ##################################################################

    def alarm_get_pons_nms_00(self,  start_date_time="", end_date_time="",
                              sort_by="alarmReceiveTime", ont_serial_number="", p=0, s=20):
        """
        Returns paged PONS-NMS alarms for provided query parameters.
            start           Start datetime      query   Long
            end             End datetime        query   Long
            sort_by          Sort by             query   String
            ontSerialNumber ONT Serial Number   query   String
            p               Start page number   query   Integer
            s               Page size           query   Integer
        """
        # get this_api = self.API_BASE + "/alarms"
        # Find PONS-NMS alarms
        self.status = 'Normal'
        this_api = ''
        dd = None
        try:
            this_api = self.API_BASE + "/alarms" + "?start=" + start_date_time + "&end=" + \
                end_date_time + "&sort_by=" + sort_by + "&ontSerialNumber=" + \
                ont_serial_number + "&p=" + ('%d' % p) + "&s=" + ('%d' % s)
            r = self.session.get(this_api, auth=(config.EON_INGESTOR_UN, config.EON_INGESTOR_PW))
            self.my_local_logger.debug("Done with API call. Status code = %d" % r.status_code)
            result = r.content
            dd = json.loads(result)
        except ValueError as e:
            self.my_local_logger.error("BRIDGE %s because %s" % (this_api, e))
            self.status = 'ValueError'
        except requests.Timeout as e:
            self.my_local_logger.error("TIMEOUT! %s" % e)
            self.status = 'Timeout'
        except requests.ConnectionError as e:
            self.my_local_logger.error(" BRIDGE %s, service may have been reset!" % e)
            self.status = 'ConnectionError'
        except requests.HTTPError as e:
            self.my_local_logger.error(" BRIDGE %s" % e)
            self.status = 'HTTPError'
        return dd

    def alarm_post_pons_nms_01(self, alarm_document=None):
        """
        Create a new PONS-NMS alarm.
        Example:
                alarmDocument= json.dumps({
                                              "alarmDescription": "",
                                              "ontSerialNumber": "",
                                              "alarmID": "",
                                              "version": "long",
                                              "alarmConditionType": "",
                                              "id": "",
                                              "guid": "",
                                              "alarmSeverity": "",
                                              "company": "",
                                              "longitude": 0,
                                              "latitude": 0,
                                              "ontAddress": "",
                                              "alarmReceiveTime": "Date",
                                              "alarmClearTime": "Date"
                                        })
        """
        # post this_api = self.API_BASE + "/alarms"
        #   Create New PONS-NMS Alarm
        self.status = 'Normal'
        this_api = self.API_BASE + "/alarms"
        dd = None
        try:
            json_alarm_document = json.dumps(alarm_document)
            r = self.session.post(this_api, json_alarm_document, headers=self.HEADERS,
                                  auth=(config.EON_INGESTOR_UN, config.EON_INGESTOR_PW),
                                  timeout=self.base_timeout)
            self.my_local_logger.debug("Done with API call. Status code = %d" % r.status_code)
            result = r.content
            dd = json.loads(result)
        except ValueError as e:
            self.my_local_logger.error("BRIDGE %s because %s" % (this_api, e))
            self.status = 'ValueError'
        except requests.Timeout as e:
            self.my_local_logger.error("TIMEOUT! %s" % e)
            self.status = 'Timeout'
        except requests.ConnectionError as e:
            self.my_local_logger.error(" BRIDGE %s, service may have been reset!" % e)
            self.status = 'ConnectionError'
        except requests.HTTPError as e:
            self.my_local_logger.error(" BRIDGE %s" % e)
            self.status = 'HTTPError'
        return dd

    def alarm_get_pons_nms_by_id_02(self, alarm_id=None):
        """
        Returns PONS-NMS Alarm that matches provided id which can be either DB id or EON360 GUID.
        Example:
                alarmId="dffdd6e5-79df-4da7-9a6d-84a8d3ead772"
        """
        # get this_api = self.API_BASE + "/alarms/{alarmId}"
        #   Find single PONS-NMS Alarm
        self.status = 'Normal'
        this_api = ''
        dd = None
        try:
            this_api = self.API_BASE + "/alarms/"+alarm_id
            r = self.session.get(this_api, auth=(config.EON_INGESTOR_UN, config.EON_INGESTOR_PW))
            self.my_local_logger.debug("Done with API call. Status code = %d" % r.status_code)
            result = r.content
            dd = json.loads(result)
        except ValueError as e:
            self.my_local_logger.error("BRIDGE %s because %s" % (this_api, e))
            self.status = 'ValueError'
        except requests.Timeout as e:
            self.my_local_logger.error("TIMEOUT! %s" % e)
            self.status = 'Timeout'
        except requests.ConnectionError as e:
            self.my_local_logger.error(" BRIDGE %s, service may have been reset!" % e)
            self.status = 'ConnectionError'
        except requests.HTTPError as e:
            self.my_local_logger.error(" BRIDGE %s." % e)
            self.status = 'HTTPError'
        return dd

    ##################################################################
    # COMPANY-PROFILES : EON company profile entry related operations
    ##################################################################
    def company_profiles_get(self, p=0, s=20):
        """
        NEW On July 14, 2015
        :param p: page number
        :param s: page size
        :return: dd
        """
        self.status = 'Normal'
        dd = None
        this_api = ''
        try:
            # http://10.123.0.27:8080/eon360/api/groomed-outages?p=0&s=20
            this_api = self.API_BASE + "/company-profiles?p=" + ('%d' % p) + "&s=" + ('%d' % s)
            r = self.session.get(this_api, auth=(config.EON_INGESTOR_UN, config.EON_INGESTOR_PW))
            self.my_local_logger.debug("Done with API call. Status code = %d" % r.status_code)
            result = r.content
            dd = json.loads(result)
        except ValueError as e:
            self.my_local_logger.error("BRIDGE %s because %s" % (this_api, e))
            self.status = 'ValueError'
        except requests.Timeout as e:
            self.my_local_logger.error("TIMEOUT! %s" % e)
            self.status = 'Timeout'
        except requests.ConnectionError as e:
            self.my_local_logger.error(" BRIDGE %s, service may have been reset!" % e)
            self.status = 'ConnectionError'
        except requests.HTTPError as e:
            self.my_local_logger.error(" BRIDGE %s." % e)
            self.status = 'HTTPError'
        return dd

    def company_profiles_post(self, company_profile_document=None):
        """
        NEW On July 14, 2015
        :param: company_profile_document = {
                                              "guid": "",
                                              "id": "",
                                              "socialTerms": [
                                                {
                                                  "weight": 0,
                                                  "term": ""
                                                }
                                              ],
                                              "averageScore": 0,
                                              "negativeVotes": "long",
                                              "company": "",
                                              "totalWeight": 0,
                                              "positiveVotes": "long",
                                              "version": "long"
                                            }
        :return:
        """
        self.status = 'Normal'
        this_api = self.API_BASE + "/company-profiles"
        dd = None
        try:
            json_eligibility_entry_document = json.dumps(company_profile_document)
            r = self.session.post(this_api, json_eligibility_entry_document, headers=self.HEADERS,
                                  auth=(config.EON_INGESTOR_UN, config.EON_INGESTOR_PW),
                                  timeout=self.base_timeout)
            self.my_local_logger.debug("Done with API call. Status code = %d" % r.status_code)
            if r.status_code > 299:
                result = '{"status_code":%d}' % r.status_code
            else:
                result = r.content
            dd = json.loads(result)
        except ValueError as e:
            self.my_local_logger.error("BRIDGE %s because %s" % (this_api, e))
            self.status = 'ValueError'
        except requests.Timeout as e:
            self.my_local_logger.error("TIMEOUT! %s" % e)
            self.status = 'Timeout'
        except requests.ConnectionError as e:
            self.my_local_logger.error(" BRIDGE %s, service may have been reset!" % e)
            self.status = 'ConnectionError'
        except requests.HTTPError as e:
            self.my_local_logger.error(" BRIDGE %s." % e)
            self.status = 'HTTPError'
        return dd

    def company_profiles_get_company_profile_id(self, company_profile_id=''):
        """
        NEW On July 14, 2015
        :param company_profile_id:
        :return:
        """
        self.status = 'Normal'
        dd = None
        this_api = ''
        try:
            this_api = self.API_BASE + "/company-profiles" + company_profile_id
            r = self.session.get(this_api, auth=(config.EON_INGESTOR_UN, config.EON_INGESTOR_PW))
            self.my_local_logger.debug("Done with API call. Status code = %d" % r.status_code)
            result = r.content
            dd = json.loads(result)
        except ValueError as e:
            self.my_local_logger.error("BRIDGE %s because %s" % (this_api, e))
            self.status = 'ValueError'
        except requests.Timeout as e:
            self.my_local_logger.error("TIMEOUT! %s" % e)
            self.status = 'Timeout'
        except requests.ConnectionError as e:
            self.my_local_logger.error(" BRIDGE %s, service may have been reset!" % e)
            self.status = 'ConnectionError'
        except requests.HTTPError as e:
            self.my_local_logger.error(" BRIDGE %s." % e)
            self.status = 'HTTPError'
        return dd

    def company_profiles_put_company_profile_id(self, company_profile_id='', company_profile_document=''):
        """
        NEW On July 14, 2015
        :param company_profile_id:
        :param: company_profile_document = {
                                              "guid": "",
                                              "id": "",
                                              "socialTerms": [
                                                {
                                                  "weight": 0,
                                                  "term": ""
                                                }
                                              ],
                                              "averageScore": 0,
                                              "negativeVotes": "long",
                                              "company": "",
                                              "totalWeight": 0,
                                              "positiveVotes": "long",
                                              "version": "long"
                                            }
        :return:
        """
        self.status = 'Normal'
        dd = None
        this_api = ''
        try:
            this_api = self.API_BASE + "/company-profiles/" + company_profile_id
            json_company_profile_document = json.dumps(company_profile_document)
            r = self.session.put(this_api, json_company_profile_document, headers=self.HEADERS,
                                 auth=(config.EON_INGESTOR_UN, config.EON_INGESTOR_PW))
            self.my_local_logger.debug("Done with API call. Status code = %d" % r.status_code)
            result = r.content
            dd = json.loads(result)
        except ValueError as e:
            self.my_local_logger.error("BRIDGE %s because %s" % (this_api, e))
            self.status = 'ValueError'
        except requests.Timeout as e:
            self.my_local_logger.error("TIMEOUT! %s" % e)
            self.status = 'Timeout'
        except requests.ConnectionError as e:
            self.my_local_logger.error(" BRIDGE %s, service may have been reset!" % e)
            self.status = 'ConnectionError'
        except requests.HTTPError as e:
            self.my_local_logger.error(" BRIDGE %s" % e)
            self.status = 'HTTPError'
        return dd

    ##################################################################
    # ELIGIBILITY : EON eligibility related operations
    ##################################################################

    def eligibilities_get_eligibilities(self, start_date_time="", end_date_time="", p=0, s=20):
        """
        Returns paged EON eligibility entries for provided query parameters.
            Parameter   Description         Parameter Type  Data Type
            start       Start datetime      query           Long
            end         End datetime        query           Long
            p           Start page number   query           Integer
            s           Page size           query           Integer
        """
        #        get this_api = self.API_BASE + "/eligibilities"
        #            Find EON Eligibility Entries
        self.status = 'Normal'
        this_api = ''
        dd = None
        try:
            this_api = self.API_BASE + "/eligibilities" + "?start=" + start_date_time + "&end=" + \
                end_date_time + "&p=" + ('%d' % p) + "&s=" + ('%d' % s)
            r = self.session.get(this_api, auth=(config.EON_INGESTOR_UN, config.EON_INGESTOR_PW))
            self.my_local_logger.debug("Done with API call. Status code = %d" % r.status_code)
            result = r.content
            dd = json.loads(result)
        except ValueError as e:
            self.my_local_logger.error("BRIDGE %s because %s" % (this_api, e))
            self.status = 'ValueError'
        except requests.Timeout as e:
            self.my_local_logger.error("TIMEOUT! %s" % e)
            self.status = 'Timeout'
        except requests.ConnectionError as e:
            self.my_local_logger.error(" BRIDGE %s, service may have been reset!" % e)
            self.status = 'ConnectionError'
        except requests.HTTPError as e:
            self.my_local_logger.error(" BRIDGE %s." % e)
            self.status = 'HTTPError'
        return dd

    def eligibilities_post_eligibilities(self, eligibility_entry_document=None):
        """
        Create a new EON eligibility entry.
        Example:
            eligibilityEntryDocument=json.dumps(
                                                {
                                                  "guid": "",
                                                  "id": "",
                                                  "ontSerialNumber": "",
                                                  "modelCoefficients": {
                                                    "values": [
                                                      0
                                                    ],
                                                    "order": "int"
                                                  },
                                                  "company": "",
                                                  "errorCode": "",
                                                  "longitude": 0,
                                                  "latitude": 0,
                                                  "alarmID": "",
                                                  "ontAddress": "",
                                                  "version": "long"
                                                }
        """
        #        post this_api = self.API_BASE + "/eligibilities"
        #            Create New EON Eligibility Entry
        self.status = 'Normal'
        this_api = self.API_BASE + "/eligibilities"
        dd = None
        try:
            json_eligibility_entry_document = json.dumps(eligibility_entry_document)
            r = self.session.post(this_api, json_eligibility_entry_document, headers=self.HEADERS,
                                  auth=(config.EON_INGESTOR_UN, config.EON_INGESTOR_PW),
                                  timeout=self.base_timeout)
            self.my_local_logger.debug("Done with API call. Status code = %d" % r.status_code)
            if r.status_code > 299:
                result = '{"status_code":%d}' % r.status_code
            else:
                result = r.content
            dd = json.loads(result)
        except ValueError as e:
            self.my_local_logger.error("BRIDGE %s because %s" % (this_api, e))
            self.status = 'ValueError'
        except requests.Timeout as e:
            self.my_local_logger.error("TIMEOUT! %s" % e)
            self.status = 'Timeout'
        except requests.ConnectionError as e:
            self.my_local_logger.error(" BRIDGE %s, service may have been reset!" % e)
            self.status = 'ConnectionError'
        except requests.HTTPError as e:
            self.my_local_logger.error(" BRIDGE %s." % e)
            self.status = 'HTTPError'
        return dd

    def eligibilities_get_eligibility_entry_id(self, eligibility_entry_id=None):
        """
        Returns EON eligibility entry that matches provided id which can be either DB id or EON360 GUID.
            Parameter           Description                 Parameter Type  Data Type
            eligibility_entry_id  EON Eligibility Entry Id    path            String
        Example:
            eligibility_entry_id=""
        """
        #        get this_api = self.API_BASE + "/eligibilities/{eligibility_entry_id}"
        #            Find single EON Eligibility Entry
        self.status = 'Normal'
        dd = None
        this_api = ''
        try:
            this_api = self.API_BASE + "/eligibilities/" + eligibility_entry_id
            r = self.session.get(this_api, auth=(config.EON_INGESTOR_UN, config.EON_INGESTOR_PW))
            self.my_local_logger.debug("Done with API call. Status code = %d" % r.status_code)
            result = r.content
            dd = json.loads(result)
        except ValueError as e:
            self.my_local_logger.error("BRIDGE %s because %s" % (this_api, e))
            self.status = 'ValueError'
        except requests.Timeout as e:
            self.my_local_logger.error("TIMEOUT! %s" % e)
            self.status = 'Timeout'
        except requests.ConnectionError as e:
            self.my_local_logger.error(" BRIDGE %s, service may have been reset!" % e)
            self.status = 'ConnectionError'
        except requests.HTTPError as e:
            self.my_local_logger.error(" BRIDGE %s." % e)
            self.status = 'HTTPError'
        return dd

    def eligibilities_put_eligibility_entry_id(self, eligibility_entry_id=None,  nearby_transformers=None):
        """
        Update EON Eligibility Model Coefficients.
        Example:
            eligibility_entry_id =
            modelCoefficients=json.dumps(
                                            {"values": [
                                                0
                                              ],
                                              "order": "int"
                                            }
                                        )
        """
        #        put this_api = self.API_BASE + "/eligibilities/{eligibility_entry_id}"
        #            Update EON Eligibility Model Coefficients
        self.status = 'Normal'
        dd = None
        this_api = ''
        try:
            this_api = self.API_BASE + "/eligibilities/" + eligibility_entry_id + "/nearbyTransformerIds"
            json_nearby_transformers = json.dumps(nearby_transformers)
            r = self.session.put(this_api, json_nearby_transformers, headers=self.HEADERS,
                                 auth=(config.EON_INGESTOR_UN, config.EON_INGESTOR_PW))
            self.my_local_logger.debug("Done with API call. Status code = %d" % r.status_code)
            result = r.content
            dd = json.loads(result)
        except ValueError as e:
            self.my_local_logger.error("BRIDGE %s because %s" % (this_api, e))
            self.status = 'ValueError'
        except requests.Timeout as e:
            self.my_local_logger.error("TIMEOUT! %s" % e)
            self.status = 'Timeout'
        except requests.ConnectionError as e:
            self.my_local_logger.error(" BRIDGE %s, service may have been reset!" % e)
            self.status = 'ConnectionError'
        except requests.HTTPError as e:
            self.my_local_logger.error(" BRIDGE %s" % e)
            self.status = 'HTTPError'
        return dd

    def eligibilities_put_eligibility_entry_id_nearby_transformer_id(self, eligibility_entry_id=None,  model_coefficients=None):
        """
        NEW On July 14, 2015
        :param eligibility_entry_id:
        :param model_coefficients:
        :return:
        """
        self.status = 'Normal'
        dd = None
        this_api = ''
        try:
            this_api = self.API_BASE + "/company-profiles/" + eligibility_entry_id
            json_model_coefficients = json.dumps(model_coefficients)
            r = self.session.put(this_api, json_model_coefficients, headers=self.HEADERS,
                                 auth=(config.EON_INGESTOR_UN, config.EON_INGESTOR_PW))
            self.my_local_logger.debug("Done with API call. Status code = %d" % r.status_code)
            result = r.content
            dd = json.loads(result)
        except ValueError as e:
            self.my_local_logger.error("BRIDGE %s because %s" % (this_api, e))
            self.status = 'ValueError'
        except requests.Timeout as e:
            self.my_local_logger.error("TIMEOUT! %s" % e)
            self.status = 'Timeout'
        except requests.ConnectionError as e:
            self.my_local_logger.error(" BRIDGE %s, service may have been reset!" % e)
            self.status = 'ConnectionError'
        except requests.HTTPError as e:
            self.my_local_logger.error(" BRIDGE %s" % e)
            self.status = 'HTTPError'
        return dd

    ##################################################################
    # GROOMED OUTAGES : EON groomed outage related operations
    ##################################################################
    def groomed_outages_get_groomed_outages(self, p=0, s=20):
        """
        :param p: page number
        :param s: page size
        :return: dd
        """
        self.status = 'Normal'
        dd = None
        this_api = ''
        try:
            # http://10.123.0.27:8080/eon360/api/groomed-outages?p=0&s=20
            this_api = self.API_BASE + "/groomed-outages?p=" + ('%d' % p) + "&s=" + ('%d' % s)
            r = self.session.get(this_api, auth=(config.EON_INGESTOR_UN, config.EON_INGESTOR_PW))
            self.my_local_logger.debug("Done with API call. Status code = %d" % r.status_code)
            result = r.content
            dd = json.loads(result)
        except ValueError as e:
            self.my_local_logger.error("BRIDGE %s because %s" % (this_api, e))
            self.status = 'ValueError'
        except requests.Timeout as e:
            self.my_local_logger.error("TIMEOUT! %s" % e)
            self.status = 'Timeout'
        except requests.ConnectionError as e:
            self.my_local_logger.error(" BRIDGE %s, service may have been reset!" % e)
            self.status = 'ConnectionError'
        except requests.HTTPError as e:
            self.my_local_logger.error(" BRIDGE %s." % e)
            self.status = 'HTTPError'
        return dd

    def groomed_outages_post_groomed_outages(self, groomed_outage_document=None):
        """
        groomed_outage_document={
                                      "timeOfEvent": 1427145646000,
                                      "eventDuration": 120000,
                                      "internalUtilityGuid": "b0e3a534-6a23-400b-bbab-eed08144cc38",
                                      "utility": {
                                        "circuitID": "39U4",
                                        "company": "CEDRAFT",
                                        "transformerID": "TR304385079_T6",
                                        "outageID": "WE14047404",
                                        "assetType": "TRANSFORMER",
                                        "address":"{\"CE Map ID\": \"None\", \"Municipality\": \"New Castle\",
                                        \"Provenance\":\"Report A\", \"Attached Assets\": [], \"Next Hop\":
                                        \"PS302355612\", \"Type\": \"HOUSE\",\"Downstream\": \"None\",
                                        \"Transformer Supply\": [\"TR302355616_T4\"], \"Upstream\":\"PS302355612\",
                                        \"Connections\": [],
                                        \"Address\":\"10 VALLEY VIEW RD, Chappaqua NY, 10514-2532\",
                                        \"Utility ID\": \"None\"}"
                                      },
                                      "algorithm": "NEAR10"
                                    }

        utility_document=          {
                                      "eventDuration": "long",
                                      "utility": {
                                        "circuitID": "",
                                        "assetType": "",
                                        "address": "",
                                        "company": "",
                                        "outageID": "",
                                        "transformerID": ""
                                      },
                                      "timeOfEvent": "Date",
                                      "company": "",
                                      "longitude": 0,
                                      "internalUtilityGuid": "",
                                      "latitude": 0,
                                      "algorithm": ""
                                    }


        :return: dd The result of the post
        """
        self.status = 'Normal'
        this_api = self.API_BASE + "/groomed-outages"
        dd = None
        try:
            json_groomed_outage_document = json.dumps(groomed_outage_document)
            r = self.session.post(this_api, json_groomed_outage_document, headers=self.HEADERS,
                                  auth=(config.EON_INGESTOR_UN, config.EON_INGESTOR_PW),
                                  timeout=self.base_timeout)
            self.my_local_logger.debug("Done with API call. Status code = %d" % r.status_code)
            if r.status_code > 299:
                result = '{"status_code":%d}' % r.status_code
            else:
                result = r.content
            dd = json.loads(result)
        except ValueError as e:
            self.my_local_logger.error("BRIDGE %s because %s" % (this_api, e))
            self.status = 'ValueError'
        except requests.Timeout as e:
            self.my_local_logger.error("TIMEOUT! %s" % e)
            self.status = 'Timeout'
        except requests.ConnectionError as e:
            self.my_local_logger.error(" BRIDGE %s, service may have been reset!" % e)
            self.status = 'ConnectionError'
        except requests.HTTPError as e:
            self.my_local_logger.error(" BRIDGE %s." % e)
            self.status = 'HTTPError'
        return dd

    def groomed_outages_get_groomed_outages_outage_id(self, outage_id=None):
        """
        :param outage_id: The outage ID to inspect
        :return: dd
        """
        self.status = 'Normal'
        dd = None
        this_api = ''
        try:
            this_api = self.API_BASE + "/groomed-outages/" + outage_id
            r = self.session.get(this_api, auth=(config.EON_INGESTOR_UN, config.EON_INGESTOR_PW))
            self.my_local_logger.debug("Done with API call. Status code = %d" % r.status_code)
            result = r.content
            dd = json.loads(result)
        except ValueError as e:
            self.my_local_logger.error("BRIDGE %s because %s" % (this_api, e))
            self.status = 'ValueError'
        except requests.Timeout as e:
            self.my_local_logger.error("TIMEOUT! %s" % e)
            self.status = 'Timeout'
        except requests.ConnectionError as e:
            self.my_local_logger.error(" BRIDGE %s, service may have been reset!" % e)
            self.status = 'ConnectionError'
        except requests.HTTPError as e:
            self.my_local_logger.error(" BRIDGE %s." % e)
            self.status = 'HTTPError'

        return dd

    def groomed_outages_put_groomed_outages_outage_id(self, outage_id=None, groomed_outage_document=None):
        """
            outage_id=""
            groomed_outage_document = {
                                                  "eventDuration": "long",
                                                  "guid": "",
                                                  "id": "",
                                                  "utility": {
                                                    "assetType": "",
                                                    "circuitID": "",
                                                    "company": "",
                                                    "outageID": "",
                                                    "transformerID": "",
                                                    "address": "",
                                                  },
                                                  "timeOfEvent": "Date",
                                                  "internalUtilityGuid": "",
                                                  "algorithm": "",
                                                  "version": "long"

                                                }
                                                New as of June 21
                                                {
                                                  "eventDuration": "long",
                                                  "utility": {
                                                    "circuitID": "",
                                                    "assetType": "",
                                                    "address": "",
                                                    "company": "",
                                                    "outageID": "",
                                                    "transformerID": ""
                                                  },
                                                  "timeOfEvent": "Date",
                                                  "company": "",
                                                  "longitude": 0,
                                                  "internalUtilityGuid": "",
                                                  "latitude": 0,
                                                  "algorithm": ""
                                                }


        :param outage_id: the id of the outage to update.
        :return: dd
        """
        #        put this_api = self.API_BASE + "/groomed-outages/{outage_id}"
        # Update Utility Groomed Outage
        self.status = 'Normal'
        this_api = self.API_BASE + "/groomed-outages/" + outage_id
        dd = None
        try:
            json_groomed_outage_document = json.dumps(groomed_outage_document)
            r = self.session.put(this_api, json_groomed_outage_document, headers=self.HEADERS,
                                 auth=(config.EON_INGESTOR_UN, config.EON_INGESTOR_PW))
            self.my_local_logger.debug("Done with API call. Status code = %d" % r.status_code)
            result = r.content
            dd = json.loads(result)
        except ValueError as e:
            self.my_local_logger.error("BRIDGE %s because %s" % (this_api, e))
            self.status = 'ValueError'
        except requests.Timeout as e:
            self.my_local_logger.error("TIMEOUT! %s" % e)
            self.status = 'Timeout'
        except requests.ConnectionError as e:
            self.my_local_logger.error(" BRIDGE %s, service may have been reset!" % e)
            self.status = 'ConnectionError'
        except requests.HTTPError as e:
            self.my_local_logger.error("BRIDGE %s" % e)
            self.status = 'HTTPError'

        return dd

    def groomed_outages_post_groomed_outages_query(self, groomed_outage_query=None, p=0, s=20, sort_by=''):
        """
        :param: groomed_outage_query = {
                                          "endTimeOfEvent": "Date",
                                          "eventDuration": "long",
                                          "utility": {
                                            "address": "",
                                            "assetType": "",
                                            "circuitID": "",
                                            "company": "",
                                            "outageID": "",
                                            "transformerID": ""
                                          },
                                          "company": "",
                                          "radius": 0,
                                          "longitude": 0,
                                          "internalUtilityGuid": "",
                                          "latitude": 0,
                                          "units": "",
                                          "algorithm": "",
                                          "beginTimeOfEvent": "Date"
                                        }
        :param: p page
        :param: s page size
        :sort_by: a string to indicate how to sort the results
          then post this to :
            http://10.123.0.27:8080/eon360/api/groomed-outages/query?p=0&s=20

        :return: dd The result of the post
        """
        self.status = 'Normal'
        if sort_by:
            this_api = self.API_BASE + "/groomed-outages/query?p=" + ('%d' % p) + "&s=" + ('%d' % s) + (
                "&sortBy=%s" % sort_by)
        else:
            this_api = self.API_BASE + "/groomed-outages/query?p=" + ('%d' % p) + "&s=" + ('%d' % s)
        dd = None
        try:
            json_groomed_outage_query = json.dumps(groomed_outage_query)
            r = self.session.post(this_api, json_groomed_outage_query, headers=self.HEADERS,
                                  auth=(config.EON_INGESTOR_UN, config.EON_INGESTOR_PW),
                                  timeout=self.base_timeout)
            self.my_local_logger.debug("Done with API call. Status code = %d" % r.status_code)
            if r.status_code > 299:
                result = '{"status_code":%d}' % r.status_code
            else:
                result = r.content
            dd = json.loads(result)
        except ValueError as e:
            self.my_local_logger.error("BRIDGE %s because %s" % (this_api, e))
            self.status = 'ValueError'
        except requests.Timeout as e:
            self.my_local_logger.error("TIMEOUT! %s" % e)
            self.status = 'Timeout'
        except requests.ConnectionError as e:
            self.my_local_logger.error(" BRIDGE %s, service may have been reset!" % e)
            self.status = 'ConnectionError'
        except requests.HTTPError as e:
            self.my_local_logger.error(" BRIDGE %s." % e)
            self.status = 'HTTPError'
        return dd

    def groomed_outages_post_groomed_outages_trigger(self, grooming_payload=None):
        """
        NEW July 2015
        :param: grooming_payload = {
                                      "spatial": "",
                                      "circuitID": "",
                                      "reputationEnabled": false,
                                      "votes": "int",
                                      "zoomT": "int",
                                      "units": "",
                                      "zoomR": "int",
                                      "assetID": "",
                                      "company": "",
                                      "temporal": "",
                                      "outageTime": "long",
                                      "radius": 0,
                                      "longitude": 0,
                                      "latitude": 0
                                    }
        :return:
        """
        self.status = 'Normal'
        this_api = self.API_BASE + "/groomed-outages/trigger"
        dd = None
        try:
            json_grooming_payload = json.dumps(grooming_payload)
            r = self.session.post(this_api, json_grooming_payload, headers=self.HEADERS,
                                  auth=(config.EON_INGESTOR_UN, config.EON_INGESTOR_PW),
                                  timeout=self.base_timeout)
            self.my_local_logger.debug("Done with API call. Status code = %d" % r.status_code)
            if r.status_code > 299:
                result = '{"status_code":%d}' % r.status_code
            else:
                result = r.content
            dd = json.loads(result)
        except ValueError as e:
            self.my_local_logger.error("BRIDGE %s because %s" % (this_api, e))
            self.status = 'ValueError'
        except requests.Timeout as e:
            self.my_local_logger.error("TIMEOUT! %s" % e)
            self.status = 'Timeout'
        except requests.ConnectionError as e:
            self.my_local_logger.error(" BRIDGE %s, service may have been reset!" % e)
            self.status = 'ConnectionError'
        except requests.HTTPError as e:
            self.my_local_logger.error(" BRIDGE %s." % e)
            self.status = 'HTTPError'
        return dd

    ##################################################################
    # OUTAGES : Utility outage related operations
    ##################################################################

    def outages_get_outages(self, start_date_time="", end_date_time="", sort_by="timeOfEvent",
                                      current_outage_only=True, company=None, p=0, s=20):
        """
        Returns paged utility outages for provided query parameters.
            Parameter           Description             Parameter Type  Data Type
            start               Start datetime          query           Long
            end                 End datetime            query           Long
            sort_by              Sort by                 query           String
            currentOutageOnly   Current outage only     query           Boolean
            company             Company                 query           String
            p                   Start page number       query           Integer
            s                   Page size               query           Integer

        Example:

        """
        #        get this_api = self.API_BASE + "/outages"
        #            Find Utility Outages
        self.status = 'Normal'
        this_api = self.API_BASE + "/outages"
        dd = None
        try:
            if current_outage_only:
                this_api = self.API_BASE + "/outages" + "?start=" + start_date_time + "&end=" + end_date_time + \
                    "&sort_by=" + sort_by + "&currentOutageOnly=True&company=" + company + \
                    "&p=" + ('%d' % p) + "&s=" + ('%d' % s)
            else:
                this_api = self.API_BASE + "/outages" + "?start=" + start_date_time + "&end=" + end_date_time + \
                    "&sort_by=" + sort_by + "&currentOutageOnly=False&company=" + company + \
                    "&p=" + ('%d' % p) + "&s=" + ('%d' % s)
            r = self.session.get(this_api, auth=(config.EON_INGESTOR_UN, config.EON_INGESTOR_PW))
            self.my_local_logger.debug("Done with API call. Status code = %d" % r.status_code)
            result = r.content
            dd = json.loads(result)
        except ValueError as e:
            self.my_local_logger.error("BRIDGE %s because %s" % (this_api, e))
            self.status = 'ValueError'
        except requests.Timeout as e:
            self.my_local_logger.error("TIMEOUT! %s" % e)
            self.status = 'Timeout'
        except requests.HTTPError as e:
            self.my_local_logger.error("BRIDGE %s" % e)
            self.status = 'HTTPError'
        except requests.ConnectionError as e:
            self.my_local_logger.error("BRIDGE %s %s" % (this_api, e))
            self.status = 'ConnectionError'
        return dd

    def outages_post_outages(self, utility_outage_document=None):
        """
        Create a new Utility outage.
        Example:
            utility_outage_document = json.dumps({
                                              "timeOfEvent": "Date",
                                              "utilityID": "",
                                              "currentState": False,
                                              "deviceAddressString": "",
                                              "version": "long",
                                              "id": "",
                                              "guid": "",
                                              "powerStatus": "",
                                              "deviceType": "",
                                              "company": "",
                                              "longitude": 0,
                                              "latitude": 0,
                                              "deviceState": False
                                            })


                        ( {
                            "powerStatus": "loss",
                            "timeOfEvent": int(time_of_last_vote),
                            "utilityID": str(waypoint['guid']), # this should be the guid of the circuit ID
                            "deviceType": "circuit",
                            "company": "CETEST",
                            "longitude":  waypoint['lat_lon'][1],
                            "latitude": waypoint['lat_lon'][0],
                            "deviceState" : False
                        }   )




        """
        # post this_api = self.API_BASE + "/outages"
        # http://10.122.116.17:28080/eon360/api/outages
        self.status = 'Normal'
        this_api = self.API_BASE + "/outages"
        dd = None
        try:
            json_utility_outage_document = json.dumps(utility_outage_document)
            r = self.session.post(this_api, json_utility_outage_document,  headers=self.HEADERS,
                                  auth=(config.EON_INGESTOR_UN, config.EON_INGESTOR_PW),
                                  timeout=self.base_timeout)
            self.my_local_logger.debug("Done with API call. Status code = %d" % r.status_code)
            if r.status_code != 200:
                self.my_local_logger.warning(
                    "status code is not 200 %s" % this_api)
            result = r.content
            dd = json.loads(result)
        except ValueError as e:
            self.my_local_logger.error("BRIDGE %s because %s" % (this_api, e))
            self.status = 'ValueError'
        except requests.Timeout as e:
            self.my_local_logger.error("TIMEOUT! %s" % e)
            self.status = 'Timeout'
        except requests.HTTPError as e:
            self.my_local_logger.error("BRIDGE %s" % e)
            self.status = 'HTTPError'
        except requests.ConnectionError as e:
            self.my_local_logger.error(" BRIDGE %s, service may have been reset!" % e)
            self.status = 'ConnectionError'

        return dd

    def outages_get_outage_outage_id(self, outage_id=None):
        """
        Returns the utility outage that matches provided id which can be either DB id or EON360 GUID.
        Parameter  Description         Parameter Type  Data Type
        outage_id  Utility Outage Id   path            String
        Example:
            outage_id = ""
        """
        #        get this_api = self.API_BASE + "/outages/{outage_id}"
        #            Find single Utility Outage
        self.status = 'Normal'
        this_api = self.API_BASE + "/outages/" + outage_id
        dd = None
        try:
            r = self.session.get(this_api, auth=(config.EON_INGESTOR_UN, config.EON_INGESTOR_PW))
            self.my_local_logger.debug("Done with API call. Status code = %d" % r.status_code)
            result = r.content
            dd = json.loads(result)
        except ValueError as e:
            self.my_local_logger.error("BRIDGE %s because %s" % (this_api, e))
            self.status = 'ValueError'
        except requests.Timeout as e:
            self.my_local_logger.error("TIMEOUT! %s" % e)
            self.status = 'Timeout'
        except requests.HTTPError as e:
            self.my_local_logger.error("BRIDGE %s" % e)
            self.status = 'HTTPError'
        except requests.ConnectionError as e:
            self.my_local_logger.error(" BRIDGE %s, service may have been reset!" % e)
            self.status = 'ConnectionError'
        return dd

    def outages_put_outage_outage_id(self, outage_id=None, utility_outage_document=None):
        """
        Updates Utility outage that matches provided id which can be either DB id or EON360 GUID.
        Example:
            outage_id=""
            utility_outage_document = json.dumps({
                                                  "timeOfEvent": "Date",
                                                  "utilityID": "",
                                                  "currentState": False,
                                                  "deviceAddressString": "",
                                                  "version": "long",
                                                  "id": "",
                                                  "guid": "",
                                                  "powerStatus": "",
                                                  "deviceType": "",
                                                  "company": "",
                                                  "longitude": 0,
                                                  "latitude": 0,
                                                  "deviceState": False
                                                })

        """
        #        put this_api = self.API_BASE + "/outages/{outage_id}"
        #            Update Utility Outage
        self.status = 'Normal'
        this_api = self.API_BASE + "/outages/" + outage_id
        dd = None
        try:
            json_utility_outage_document = json.dumps(utility_outage_document)
            r = self.session.put(this_api, json_utility_outage_document, headers=self.HEADERS,
                                 auth=(config.EON_INGESTOR_UN, config.EON_INGESTOR_PW))
            self.my_local_logger.debug("Done with API call. Status code = %d" % r.status_code)
            result = r.content
            dd = json.loads(result)
        except ValueError as e:
            self.my_local_logger.error("BRIDGE %s because %s" % (this_api, e))
            self.status = 'ValueError'
        except requests.Timeout as e:
            self.my_local_logger.error("TIMEOUT! %s" % e)
            self.status = 'Timeout'
        except requests.HTTPError as e:
            self.my_local_logger.error("BRIDGE %s" % e)
            self.status = 'HTTPError'
        except requests.ConnectionError as e:
            self.my_local_logger.error(" BRIDGE %s, service may have been reset!" % e)
            self.status = 'ConnectionError'
        return dd

    ##################################################################
    # QUERY : EON query related operations
    ##################################################################

    def query_post_query(self, query_parameter=None):  # , p=0, s=20):
        """
        Find EON data items that match to the search parameter.
        itemType can be ALL, ELIGIBILITY, ALARM, UTILITY
        Example:
            queryParameter= json.dumps( {
                                      "itemType": "ALL",
                                      "circle": {
                                              "latitude": 41.524081,
                                              "longitude": -74.396216,
                                              "radius": 1.0,
                                              "unit": "MILES"},
                                      "pageParameter": {
                                              "page": 1,
                                              "size": 20}})

            item types can be "ELIGIBILITY", "ALL", "ALARM", "UTILITY"
        """
        # post this_api = self.API_BASE + "/query"
        #            Query EON Data Items
        # http://10.122.116.17:28080/eon360/api/query
        self.status = 'Normal'
        this_api = self.API_BASE + "/query"  # ?p=" + ('%d' % p) + "&s=" + ('%d' % s)
        dd = None
        json_query_parameter = query_parameter  # json.dumps(query_parameter)
        self.my_local_logger.debug("json_query_parameter = %s" % json_query_parameter)
        try:
            self.my_local_logger.debug("making post API call")
            self.my_local_logger.debug("Trying to post to API %s with query_parameter=%s" %
                                       (this_api, json_query_parameter))
            # Something weird is happening here
            # time.sleep(0.1)
            r = self.session.post(this_api, json_query_parameter,  headers=self.HEADERS,
                                  auth=(config.EON_INGESTOR_UN, config.EON_INGESTOR_PW),
                                  timeout=self.base_timeout)
            # json content is here
            self.my_local_logger.debug("Done with API call. Status code = %d" % r.status_code)
            result = r.content
            dd = json.loads(result)
        except ValueError as e:
            self.my_local_logger.error("BRIDGE %s because %s" % (this_api, e))
            self.status = 'ValueError'
        except requests.ConnectionError as e:
            self.my_local_logger.error(" BRIDGE %s, service may have been reset!" % e)
            self.status = 'ConnectionError'
        except requests.Timeout as e:
            self.my_local_logger.error("TIMEOUT! %s, json_query_parameter = %s" % (e, json_query_parameter))
            self.status = 'Timeout'
        except requests.HTTPError as e:
            self.my_local_logger.error("aborting! %s" % e)
            self.status = 'HTTPError'
            print "query_post_query failed"
        return dd

    def query_post_query_alarms(self, alarm_ids=None,  p=0, s=20):
        """
        Parameter   Description         Parameter Type  Data Type
        p           Start page number   query           Integer
        s           Page size           query           Integer

        ontSerialNumbers    ONT Serial Num
        """
        self.status = 'Normal'
        this_api = self.API_BASE + "/query/alarms?p=" + ('%d' % p) + "&s=" + ('%d' % s)
        dd = None
        try:
            json_alarm_ids = json.dumps(alarm_ids)
            r = self.session.post(this_api, json_alarm_ids, headers=self.HEADERS,
                                  auth=(config.EON_INGESTOR_UN, config.EON_INGESTOR_PW),
                                  timeout=self.base_timeout)
            self.my_local_logger.debug("Done with API call. Status code = %d" % r.status_code)
            result = r.content
            dd = json.loads(result)
        except ValueError as e:
            self.my_local_logger.error("BRIDGE %s because %s" % (this_api, e))
            self.status = 'ValueError'
        except requests.Timeout as e:
            self.my_local_logger.error("TIMEOUT! %s" % e)
            self.status = 'Timeout'
        except requests.ConnectionError as e:
            self.my_local_logger.error(" BRIDGE %s, service may have been reset!" % e)
            self.status = 'ConnectionError'
        except requests.HTTPError as e:
            self.my_local_logger.error(" BRIDGE %s." % e)
            self.status = 'HTTPError'
        return dd

    def query_post_query_eligibilities(self, box=None, p=0, s=20):
        """
        Find eligibility data items that are within a given box.
        Example:
            box={"minLatitude":41.24311355965124,
                 "maxLatitude":41.32836547490742,
                 "minLongitude":-73.9596228682787,
                 "maxLongitude":-73.81992416089541}
        """
        #        post this_api = self.API_BASE + "/query/utilities"
        #            Query Utility Data Items
        self.status = 'Normal'
        this_api = self.API_BASE + "/query/utilities"
        dd = None
        if box is not None:
            this_api = self.API_BASE + "/query/eligibilities?p=" + ('%d' % p) + "&s=" + ('%d' % s)
            try:
                json_utility_ids = json.dumps(box)
                r = self.session.post(this_api, json_utility_ids, headers=self.HEADERS,
                                      auth=(config.EON_INGESTOR_UN, config.EON_INGESTOR_PW),
                                      timeout=self.base_timeout)
                self.my_local_logger.debug("Done with API call. Status code = %d" % r.status_code)
                result = r.content
                dd = json.loads(result)
            except ValueError as e:
                self.my_local_logger.error("BRIDGE %s because %s" % (this_api, e))
                self.status = 'ValueError'
            except requests.Timeout as e:
                self.my_local_logger.error("TIMEOUT! %s" % e)
                self.status = 'Timeout'
            except requests.ConnectionError as e:
                self.my_local_logger.error(" BRIDGE %s, service may have been reset!" % e)
                self.status = 'ConnectionError'
            except requests.HTTPError as e:
                self.my_local_logger.error(" BRIDGE %s." % e)
                self.status = 'HTTPError'
        return dd

    def query_post_query_utilities(self, utility_ids=None):
        """
        Find utility data items that match provided list of GUIDs.
        Example:
            utility_ids=["","",""]
        """
        #        post this_api = self.API_BASE + "/query/utilities"
        #            Query Utility Data Items
        self.status = 'Normal'
        this_api = self.API_BASE + "/query/utilities"
        dd = None
        try:
            json_utility_ids = json.dumps(utility_ids)
            r = self.session.post(this_api, json_utility_ids, headers=self.HEADERS,
                                  auth=(config.EON_INGESTOR_UN, config.EON_INGESTOR_PW),
                                  timeout=self.base_timeout)
            self.my_local_logger.debug("Done with API call. Status code = %d" % r.status_code)
            result = r.content
            dd = json.loads(result)
        except ValueError as e:
            self.my_local_logger.error("BRIDGE %s because %s" % (this_api, e))
            self.status = 'ValueError'
        except requests.Timeout as e:
            self.my_local_logger.error("TIMEOUT! %s" % e)
            self.status = 'Timeout'
        except requests.ConnectionError as e:
            self.my_local_logger.error(" BRIDGE %s, service may have been reset!" % e)
            self.status = 'ConnectionError'
        except requests.HTTPError as e:
            self.my_local_logger.error(" BRIDGE %s." % e)
            self.status = 'HTTPError'
        return dd

    ##################################################################
    # TEST : Test operations
    ##################################################################
    @staticmethod
    def test_get_test_login(self):
        """
        get this_api = self.API_BASE + "/test/login"
        test View
        :return:
        """
        self.status = 'Normal'
        dd = None
        this_api = ''
        try:
            this_api = self.API_BASE + "/test"
            r = self.session.get(this_api, auth=(config.EON_INGESTOR_UN, config.EON_INGESTOR_PW))
            self.my_local_logger.debug("Done with API call. Status code = %d" % r.status_code)
            result = r.content
            dd = json.loads(result)
        except ValueError as e:
            self.my_local_logger.error("BRIDGE %s because %s" % (this_api, e))
            self.status = 'ValueError'
        except requests.Timeout as e:
            self.my_local_logger.error("TIMEOUT! %s" % e)
            self.status = 'Timeout'
        except requests.ConnectionError as e:
            self.my_local_logger.error(" BRIDGE %s, service may have been reset!" % e)
            self.status = 'ConnectionError'
        except requests.HTTPError as e:
            self.my_local_logger.error(" BRIDGE %s." % e)
            self.status = 'HTTPError'
        return dd

    ##################################################################
    # TOOLS : EON common services
    ##################################################################
    def tools_get_outage_region(self, start_date_time="", end_date_time="", company=None):
        """
        Returns outage region for provided query parameters.
            Parameter   Description     Parameter Type  Data Type
            start       Start datetime  query           Long
            end         End datetime    query           Long
            company     Company         query           String
        Example:

        """
        #        get this_api = self.API_BASE + "/tools/outage-region"
        #            Find Outage Region
        self.status = 'Normal'
        dd = None
        this_api = ''
        try:
            this_api = self.API_BASE + "/tools/outage-region" + "?start=" + start_date_time +\
                "&end=" + end_date_time + "&company=" + company
            r = self.session.get(this_api, auth=(config.EON_INGESTOR_UN, config.EON_INGESTOR_PW))
            self.my_local_logger.debug("Done with API call. Status code = %d" % r.status_code)
            result = r.content
            dd = json.loads(result)
        except ValueError as e:
            self.my_local_logger.error("BRIDGE %s because %s" % (this_api, e))
            self.status = 'ValueError'
        except requests.Timeout as e:
            self.my_local_logger.error("TIMEOUT! %s" % e)
            self.status = 'Timeout'
        except requests.ConnectionError as e:
            self.my_local_logger.error(" BRIDGE %s, service may have been reset!" % e)
            self.status = 'ConnectionError'
        except requests.HTTPError as e:
            self.my_local_logger.error(" BRIDGE %s." % e)
            self.status = 'HTTPError'
        return dd

    ##################################################################
    # TWEETS: EON tweet entry related operations
    ##################################################################
    def tweets_post_tweets(self, tweet_document=None):
        """
        NEW on July 15, 2015
        :param: tweet_document = {
                                  "guid": "",
                                  "id": "",
                                  "tweetDate": "Date",
                                  "company": "",
                                  "tweet": "",
                                  "longitude": 0,
                                  "tweetJSON": "",
                                  "latitude": 0,
                                  "sentimentScore": 0,
                                  "similarityScore": 0,
                                  "version": "long"
                                }
        :return:
        """
        self.status = 'Normal'
        this_api = self.API_BASE + "/tweets"
        dd = None
        try:
            json_tweet_document = json.dumps(tweet_document)
            r = self.session.post(this_api, json_tweet_document, headers=self.HEADERS,
                                  auth=(config.EON_INGESTOR_UN, config.EON_INGESTOR_PW),
                                  timeout=self.base_timeout)
            self.my_local_logger.debug("Done with API call. Status code = %d" % r.status_code)
            result = r.content
            dd = json.loads(result)
        except ValueError as e:
            self.my_local_logger.error("BRIDGE %s because %s" % (this_api, e))
            self.status = 'ValueError'
        except requests.Timeout as e:
            self.my_local_logger.error("TIMEOUT! %s" % e)
            self.status = 'Timeout'
        except requests.ConnectionError as e:
            self.my_local_logger.error(" BRIDGE %s, service may have been reset!" % e)
            self.status = 'ConnectionError'
        except requests.HTTPError as e:
            self.my_local_logger.error(" BRIDGE %s." % e)
            self.status = 'HTTPError'
        return dd

    def tweets_get_tweets(self, start_date_time="", end_date_time="", company="", p=0, s=20):
        """
        NEW on July 15, 2015
        :param start_date_time:
        :param end_date_time:
        :param company:
        :param p:
        :param s:
        :return:
        """
        self.status = 'Normal'
        dd = None
        this_api = ''
        try:
            this_api = self.API_BASE + "/tweets" + "?start=" + start_date_time + "&end=" + end_date_time +\
                "&company=" + company + "&p=" + ('%d' % p) + "&s=" + ('%d' % s)
            r = self.session.get(this_api, auth=(config.EON_INGESTOR_UN, config.EON_INGESTOR_PW))
            self.my_local_logger.debug("Done with API call. Status code = %d" % r.status_code)
            result = r.content
            dd = json.loads(result)
        except ValueError as e:
            self.my_local_logger.error("BRIDGE %s because %s" % (this_api, e))
            self.status = 'ValueError'
        except requests.Timeout as e:
            self.my_local_logger.error("TIMEOUT! %s" % e)
            self.status = 'Timeout'
        except requests.ConnectionError as e:
            self.my_local_logger.error(" BRIDGE %s, service may have been reset!" % e)
            self.status = 'ConnectionError'
        except requests.HTTPError as e:
            self.my_local_logger.self.my_local_logger.error(" BRIDGE %s." % e)
            self.status = 'HTTPError'
        return dd

    def tweets_get_tweets_tweet_id(self, tweed_id=None):
        """
        NEW on July 15, 2015
        :param: tweet_id
        :return:
        """
        #        get this_api = self.API_BASE + "/tweets/{tweet_id}"
        #            Find single EON Tweet Entry
        self.status = 'Normal'
        dd = None
        this_api = ''
        try:
            this_api = self.API_BASE + "/tweets/" + tweed_id
            r = self.session.get(this_api, auth=(config.EON_INGESTOR_UN, config.EON_INGESTOR_PW))
            self.my_local_logger.debug("Done with API call. Status code = %d" % r.status_code)
            result = r.content
            dd = json.loads(result)
        except ValueError as e:
            self.my_local_logger.error("BRIDGE %s because %s" % (this_api, e))
            self.status = 'ValueError'
        except requests.Timeout as e:
            self.my_local_logger.error("TIMEOUT! %s" % e)
            self.status = 'Timeout'
        except requests.ConnectionError as e:
            self.my_local_logger.error(" BRIDGE %s, service may have been reset!" % e)
            self.status = 'ConnectionError'
        except requests.HTTPError as e:
            self.my_local_logger.error(" BRIDGE %s." % e)
            self.status = 'HTTPError'
        return dd

    ##################################################################
    # UTILITIES : EON utility entry related operations
    ##################################################################
    def utilities_post_utilities(self, utility_document=None):
        """
        Create a new EON utility entry.
        Example:
            utility_document=json.dumps({
                                  "circuitID": "",
                                  "downStreamItemID": "",
                                  "version": "long",
                                  "id": "",
                                  "guid": "",
                                  "company": "",
                                  "errorCode": "",
                                  "upStreamItemID": "",
                                  "longitude": 0,
                                  "latitude": 0,
                                  "transformerID": "",
                                  "serviceAddress": "",
                                  "eligibilityList": [
                                    {
                                      "guid": "",
                                      "id": "",
                                      "ontSerialNumber": "",
                                      "modelCoefficients": {
                                        "values": [
                                          0
                                        ],
                                        "order": "int"
                                      },
                                      "company": "",
                                      "errorCode": "",
                                      "longitude": 0,
                                      "latitude": 0,
                                      "alarmID": "",
                                      "ontAddress": "",
                                      "version": "long"
                                    }
                                  ]
                                })
        """
        #        post this_api = self.API_BASE + "/utilities"
        #            Create New EON Utility Entry
        self.status = 'Normal'
        this_api = self.API_BASE + "/utilities"
        dd = None
        try:
            json_utility_document = json.dumps(utility_document)
            r = self.session.post(this_api, json_utility_document, headers=self.HEADERS,
                                  auth=(config.EON_INGESTOR_UN, config.EON_INGESTOR_PW),
                                  timeout=self.base_timeout)
            self.my_local_logger.debug("Done with API call. Status code = %d" % r.status_code)
            if r.status_code > 299:
                result = '{"status_code":%d}' % r.status_code
            else:
                result = r.content
            dd = json.loads(result)
        except ValueError as e:
            self.my_local_logger.error("BRIDGE %s because %s" % (this_api, e))
            self.status = 'ValueError'
        except requests.Timeout as e:
            self.my_local_logger.error("TIMEOUT! %s" % e)
            self.status = 'Timeout'
        except requests.ConnectionError as e:
            self.my_local_logger.error(" BRIDGE %s, service may have been reset!" % e)
            self.status = 'ConnectionError'
        except requests.HTTPError as e:
            self.my_local_logger.error(" BRIDGE %s." % e)
            self.status = 'HTTPError'
        return dd

    # This might also be referenced as utilities_get_61
    def utilities_get_utilities(self, start_date_time="", end_date_time="", company="", p=0, s=20):
        """
        Returns paged EON utility entries for provided query parameters.
            Parameter   Description         Parameter Type  Data Type
            start       Start datetime      query           Long
            end         End datetime        query           Long
            company     Company             query           String
            p           Start page number   query           Integer
            s           Page size           query           Integer
        Example:
        """
        #        get this_api = self.API_BASE + "/utilities"
        #            Find EON Utility Entries
        self.status = 'Normal'
        dd = None
        this_api = ''
        try:
            this_api = self.API_BASE + "/utilities" + "?start=" + start_date_time + "&end=" + end_date_time +\
                "&company=" + company + "&p=" + ('%d' % p) + "&s=" + ('%d' % s)
            r = self.session.get(this_api, auth=(config.EON_INGESTOR_UN, config.EON_INGESTOR_PW))
            self.my_local_logger.debug("Done with API call. Status code = %d" % r.status_code)
            result = r.content
            dd = json.loads(result)
        except ValueError as e:
            self.my_local_logger.error("BRIDGE %s because %s" % (this_api, e))
            self.status = 'ValueError'
        except requests.Timeout as e:
            self.my_local_logger.error("TIMEOUT! %s" % e)
            self.status = 'Timeout'
        except requests.ConnectionError as e:
            self.my_local_logger.error(" BRIDGE %s, service may have been reset!" % e)
            self.status = 'ConnectionError'
        except requests.HTTPError as e:
            self.my_local_logger.self.my_local_logger.error(" BRIDGE %s." % e)
            self.status = 'HTTPError'
        return dd

    def utilities_get_utilities_utility_id(self, utility_id=None):
        """
        Returns EON utility entry that matches provided id which can be either DB id or EON360 GUID.
            Parameter   Description             Parameter Type  Data Type
            utilityId   EON Utility Entry Id    path            String
        Example:
        """
        #        get this_api = self.API_BASE + "/utilities/{utility_id}"
        #            Find single EON Utility Entry
        self.status = 'Normal'
        dd = None
        this_api = ''
        try:
            this_api = self.API_BASE + "/utilities/" + utility_id
            r = self.session.get(this_api, auth=(config.EON_INGESTOR_UN, config.EON_INGESTOR_PW))
            self.my_local_logger.debug("Done with API call. Status code = %d" % r.status_code)
            result = r.content
            dd = json.loads(result)
        except ValueError as e:
            self.my_local_logger.error("BRIDGE %s because %s" % (this_api, e))
            self.status = 'ValueError'
        except requests.Timeout as e:
            self.my_local_logger.error("TIMEOUT! %s" % e)
            self.status = 'Timeout'
        except requests.ConnectionError as e:
            self.my_local_logger.error(" BRIDGE %s, service may have been reset!" % e)
            self.status = 'ConnectionError'
        except requests.HTTPError as e:
            self.my_local_logger.error(" BRIDGE %s." % e)
            self.status = 'HTTPError'
        return dd

    def utilities_post_utilities_utility_id_downstream_downstream_id(self, utility_id=None, down_stream_id=None):
        """
        Set downstream item for the given utility.
            Parameter       Description             Parameter Type  Data Type
            utility_id      EON utilityID          path            String
            down_stream_id  Upstream utilityID     path            String
        Example:

        """
        #        post this_api = self.API_BASE + "/utilities/{utility_id}/downstream/{downStreamId}"
        #            Set EON Utility Downstream
        self.status = 'Normal'
        dd = None
        this_api = ''
        try:
            this_api = self.API_BASE + "/utilities/" + utility_id + "/downstream/" + down_stream_id
            r = self.session.post(this_api, "", headers=self.HEADERS,
                                  auth=(config.EON_INGESTOR_UN, config.EON_INGESTOR_PW),
                                  timeout=self.base_timeout)
            self.my_local_logger.debug("Done with API call. Status code = %d" % r.status_code)
            result = r.content
            dd = json.loads(result)
        except ValueError as e:
            self.my_local_logger.error("BRIDGE %s because %s" % (this_api, e))
            self.status = 'ValueError'
        except requests.Timeout as e:
            self.my_local_logger.error("TIMEOUT! %s" % e)
            self.status = 'Timeout'
        except requests.ConnectionError as e:
            self.my_local_logger.error(" BRIDGE %s, service may have been reset!" % e)
            self.status = 'ConnectionError'
        except requests.HTTPError as e:
            self.my_local_logger.error(" BRIDGE %s." % e)
            self.status = 'HTTPError'
        return dd

    def utilities_post_utilities_utility_id_eligibilities(self, utility_id=None, eligibility_ids=None):
        """
        Associate the given utility with list of eligibility items.
            Parameter       Description     Parameter Type  Data Type
            utilityId       EON Utility Id  path            String
            eligibilityIds  GUID list of the eligibility items to be associated with this ID
        Example:
            utilityId="2aaea56e-7499-4026-b052-9ca0438e3106"
            eligibilityIds=["b585681a-1eb4-4683-9beb-0e8fa5af0c73","ecb4931d-a4e2-44e8-bc67-d1fe9043dee9"]

        """
        #        post this_api = self.API_BASE + "/utilities/{utilityId}/eligibilities"
        #            Set EON Utility Eligibility Associations
        self.status = 'Normal'

        dd = None
        this_api = ''
        try:
            json_eligibility_ids = json.dumps(eligibility_ids)
            this_api = self.API_BASE + "/utilities/" + utility_id + "/eligibilities"
            r = self.session.post(this_api, json_eligibility_ids, headers=self.HEADERS,
                                  auth=(config.EON_INGESTOR_UN, config.EON_INGESTOR_PW),
                                  timeout=self.base_timeout)
            self.my_local_logger.debug("Done with API call. Status code = %d" % r.status_code)
            result = r.content
            dd = json.loads(result)
        except ValueError as e:
            self.my_local_logger.error("BRIDGE %s because %s" % (this_api, e))
            self.status = 'ValueError'
        except requests.Timeout as e:
            self.my_local_logger.error("TIMEOUT! %s" % e)
            self.status = 'Timeout'
        except requests.ConnectionError as e:
            self.my_local_logger.error(" BRIDGE %s, service may have been reset!" % e)
            self.status = 'ConnectionError'
        except requests.HTTPError as e:
            self.my_local_logger.error(" BRIDGE %s." % e)
            self.status = 'HTTPError'
        return dd

    def utilities_post_utilities_utility_id_upstream_upstream_id(self, utility_id=None, upstream_id=None):
        """
        Set upstream item for the given utility.
            Parameter   Description             Parameter Type  Data Type
            utilityId   EON Utility Id          path            String
            upStreamId  Upstream Utility Id     path            String
        Example:
        """
        #        post this_api = self.API_BASE + "/utilities/{utilityId}/upstream/{upStreamId}"
        #            Set EON Utility Upstream
        self.status = 'Normal'
        dd = None
        this_api = ''
        try:
            this_api = self.API_BASE + "/utilities/" + utility_id + "/upstream/" + upstream_id
            r = self.session.post(this_api, "", headers=self.HEADERS,
                                  auth=(config.EON_INGESTOR_UN, config.EON_INGESTOR_PW),
                                  timeout=self.base_timeout)
            self.my_local_logger.debug("Done with API call. Status code = %d" % r.status_code)
            result = r.content
            dd = json.loads(result)
        except ValueError as e:
            self.my_local_logger.error("BRIDGE %s because %s" % (this_api, e))
            self.status = 'ValueError'
        except requests.Timeout as e:
            self.my_local_logger.error("TIMEOUT! %s" % e)
            self.status = 'Timeout'
        except requests.ConnectionError as e:
            self.my_local_logger.error(" BRIDGE %s, service may have been reset!" % e)
            self.status = 'ConnectionError'
        except requests.HTTPError as e:
            self.my_local_logger.error(" BRIDGE %s." % e)
            self.status = 'HTTPError'
        return dd

    def utilities_get_utilities_circuits_ids(self, company="", search_string=None):
        """
        Returns all distinct circuit IDs.
        :param company:
        :param search_string:
        :return: dd
        """
        self.status = 'Normal'
        dd = None
        this_api = ''
        try:
            params = "?company=" + company
            if search_string is not None:
                params += "&%s" % search_string
            this_api = self.API_BASE + "/utilities/circuitIDs" + params
            r = self.session.get(this_api, auth=(config.EON_INGESTOR_UN, config.EON_INGESTOR_PW))
            self.my_local_logger.debug("Done with API call. Status code = %d" % r.status_code)
            result = r.content
            dd = json.loads(result)
        except ValueError as e:
            self.my_local_logger.error("BRIDGE %s because %s" % (this_api, e))
            self.status = 'ValueError'
        except requests.Timeout as e:
            self.my_local_logger.error("TIMEOUT! %s" % e)
            self.status = 'Timeout'
        except requests.ConnectionError as e:
            self.my_local_logger.error(" BRIDGE %s, service may have been reset!" % e)
            self.status = 'ConnectionError'
        except requests.HTTPError as e:
            self.my_local_logger.error(" BRIDGE %s." % e)
            self.status = 'HTTPError'
        return dd

    def utilities_get_utilities_circuits_circuit_id(self, circuit_id=None, company="",  p=0, s=20):
        """
        Returns paged EON utility entries with provided circuit ID.
            Parameter   Description         Parameter Type  Data Type
            circuitID   EON Circuit Id      path            String
            company     Company             query           String
            p           Start page number   query           Integer
            s           Page size           query           Integer
        Example:
        """
        #        get this_api = self.API_BASE + "/utilities/circuits/{circuitID}"
        #            Find EON Utility Entries with given circuit ID
        self.status = 'Normal'

        dd = None
        this_api = ''
        try:
            this_api = self.API_BASE + "/utilities/circuits/" + circuit_id + "?company=" + company +\
                "&p=" + ('%d' % p) + "&s=" + ('%d' % s)
            r = self.session.get(this_api, auth=(config.EON_INGESTOR_UN, config.EON_INGESTOR_PW))
            self.my_local_logger.debug("Done with API call. Status code = %d" % r.status_code)
            # r = requests.get(call_api, auth=(config.EON_INGESTOR_UN, config.EON_INGESTOR_PW))
            # json content is
            if r.status_code > 299:
                result = '{"status_code":%d}' % r.status_code
            else:
                result = r.content
            dd = json.loads(result)
        except ValueError as e:
            self.my_local_logger.error("BRIDGE %s because %s" % (this_api, e))
            self.status = 'ValueError'
        except requests.Timeout as e:
            self.my_local_logger.error("TIMEOUT! %s" % e)
            self.status = 'Timeout'
        except requests.ConnectionError as e:
            self.my_local_logger.error(" BRIDGE %s, service may have been reset!" % e)
            self.status = 'ConnectionError'
        except requests.HTTPError as e:
            self.my_local_logger.error(" BRIDGE %s." % e)
            self.status = 'HTTPError'
        return dd

    def utilities_get_transformer_ids(self, company="", search_string=None, circuit_id=None):
        """
        Returns all distinct transformer IDs. (asset IDs)
        http://10.123.0.27:8080/eon360/api/utilities/transformerIDs?company=CEDRAFT
        :param company: (required)
        :param search_string:
        :param circuit_id:
        :return: dd
        """
        self.status = 'Normal'
        dd = None
        this_api = ''
        try:
            params = "?company=" + company
            if search_string is not None:
                params += "&%s" % search_string
            if circuit_id is not None:
                params += "&%s" % circuit_id

            this_api = self.API_BASE + "/utilities/transformerIDs" + params
            r = self.session.get(this_api, auth=(config.EON_INGESTOR_UN, config.EON_INGESTOR_PW))
            self.my_local_logger.debug("Done with API call. Status code = %d" % r.status_code)
            result = r.content
            dd = json.loads(result)
        except ValueError as e:
            self.my_local_logger.error("BRIDGE %s because %s" % (this_api, e))
            self.status = 'ValueError'
        except requests.Timeout as e:
            self.my_local_logger.error("TIMEOUT! %s" % e)
            self.status = 'Timeout'
        except requests.ConnectionError as e:
            self.my_local_logger.error(" BRIDGE %s, service may have been reset!" % e)
            self.status = 'ConnectionError'
        except requests.HTTPError as e:
            self.my_local_logger.error(" BRIDGE %s." % e)
            self.status = 'HTTPError'
        return dd

    def utilities_get_transformers_transformer_id(self, transformer_id=None, company="",  p=0, s=20):
        """
        Returns paged EON utility entries with provided transformer ID.
            Parameter       Description         Parameter Type  Data Type
            transformerID   EON Circuit Id      path            String
            company         Company             query           String
            p               Start page number   query           Integer
            s               Page size           query           Integer
        Example:

        """
        #        get this_api = self.API_BASE + "/utilities/transformers/{transformerID}"
        #            Find EON Utility Entries with given transformer ID
        self.status = 'Normal'

        dd = None
        this_api = ''
        try:
            this_api = self.API_BASE + "/utilities/transformers/" + transformer_id + "?company=" + company + \
                "&p=" + ('%d' % p) + "&s=" + ('%d' % s)
            r = self.session.get(this_api, auth=(config.EON_INGESTOR_UN, config.EON_INGESTOR_PW))
            self.my_local_logger.debug("Done with API call. Status code = %d" % r.status_code)
            result = r.content
            dd = json.loads(result)
        except ValueError as e:
            self.my_local_logger.error("BRIDGE %s because %s" % (this_api, e))
            self.status = 'ValueError'
        except requests.Timeout as e:
            self.my_local_logger.error("TIMEOUT! %s" % e)
            self.status = 'Timeout'
        except requests.ConnectionError as e:
            self.my_local_logger.error(" BRIDGE %s, service may have been reset!" % e)
            self.status = 'ConnectionError'
        except requests.HTTPError as e:
            self.my_local_logger.error(" BRIDGE %s." % e)
            self.status = 'HTTPError'
        return dd

    ################################################################
    # CONVENIENCE FUNCTIONS
    ################################################################
    def query_eon_area_a0(self, lat, lon, radius, query_type="ALL"):
        """
        Ask the EON API for onts, circuits and transformers for a given lat, lon and radius
        Returns a group of items that are inside the circle with a given center (lat, lon) and
        radius.
        Note: convert the time units in the ONT event list into minutes by dividing by 60000
        :param lat: Latitude
        :param lon: Longitude
        :param radius: Radius (in config units)
        :param: query_type: The type of query "ALL", "ALARM", "ELIGIBILITY"
        :return: this_cell # A hexagonal cell dictionary
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
              "pageParmeter": {
                "page": 0,
                "size": 100
              }
            }
        This will return a data structure like this
        dd['eligibility']['dataItems']
        dd['alarm']['dataItems']
        dd['utility']['dataItems']
        """

        # query_database(center,radius, circuits,transformers,onts)
        # Returns a group of items that are inside the circle with a given center (lat, lon) and
        # radius.
        #
        # # Test is:
        self.status = 'Normal'
        o_guids = []
        o_ids = []
        o_these_lat_lons = []
        o_array_states = []
        c_ids = []
        c_these_lat_lons = []
        c_array_states = []
        x_ids = []
        x_these_lat_lons = []
        x_array_states = []

        # Loop here until no more utility components of the first collection are found
        page_number = 0
        page_size = 20
        query_parameter = json.dumps({"itemType": query_type,
                                      "circle": {"longitude": lon,
                                                 "latitude": lat,
                                                 "radius": radius, "unit": config.RADIUS_UNITS},
                                      "pageParameter": {"page": page_number, "size": page_size}})

        dd = self.query_post_query(query_parameter=query_parameter)

        more_pages = True
        while more_pages:
            # This is the ONTs loop through them and find all the ONTs in the area
            for this_ont in dd['eligibility']['dataItems']:
                o_guids.append(this_ont['guid'])
                o_ids.append(this_ont['ontSerialNumber'])
                o_these_lat_lons.append([this_ont['latitude'], this_ont['longitude']])
                device_state_vector = [[0, EonApiBridge.ON]]
                for thisAlarm in dd['alarm']['dataItems']:
                    if this_ont['guid'] == thisAlarm['guid']:
                        alarm_on_time = thisAlarm['alarmReceiveTime']
                        alarm_off_time = thisAlarm['alarmClearTime']
                        # Some logic to determine the currect state of the alarm
                        # The state vector will be an array of time value pairs that represents the
                        # known state of this ONT
                        # Since we can get many state transitions for teh same ONT in the same radius during the
                        # same query then we
                        # need to construct a waveform of states.
                        # Assume the ONT is ON at T=0
                        device_state_vector = [[0, EonApiBridge.ON]]
                        if alarm_on_time is not None:
                            # The alarm was triggered once, lets see if its cleared
                            if alarm_off_time is not None:
                                # The alarm was cleared. Let determine which came first
                                if alarm_off_time > alarm_on_time:
                                    device_state_vector.append([alarm_on_time,  EonApiBridge.OFF])
                                    device_state_vector.append([alarm_off_time,  EonApiBridge.ON])
                                    # device is currently ON
                                else:
                                    device_state_vector.append([alarm_off_time,  EonApiBridge.ON])
                                    device_state_vector.append([alarm_on_time,  EonApiBridge.OFF])
                                    # device is currently OFF
                            else:
                                # The alarmOff is None so it never cleared and the device is off
                                device_state_vector.append([alarm_on_time,  EonApiBridge.OFF])
                        else:
                            # Alarm was never set so just assume the device is powered on
                            # This case should never happen on the MQ bus but could happen when just querying the ONTs
                            print " this is an unreachable point"
                # collect the state of this alarm
                o_array_states.append(device_state_vector)

            for this_item in dd['utility']['dataItems']:
                c_ids.append(this_item['circuitID'])
                x_ids.append(this_item['transformerID'])
                c_these_lat_lons.append([this_item['latitude'], this_item['longitude']])
                x_these_lat_lons.append([this_item['latitude'], this_item['longitude']])
                dummy_circuit_state = 1
                c_array_states.append(dummy_circuit_state)
                dummy_transformer_state = 1
                x_array_states.append(dummy_transformer_state)
            # ############################
            # # Look for the next page  # #
            # ############################
            if (dd['utility']['hasNextPage'] is True) or \
                    (dd['alarm']['hasNextPage'] is True) or \
                    (dd['eligibility']['hasNextPage'] is True):
                self.my_local_logger.debug("Collecting next page for this message")
                page_number += 1
                more_pages = True
                query_parameter = json.dumps({"itemType": query_type,
                                              "circle": {"longitude": lon,
                                                         "latitude": lat,
                                                         "radius": radius,
                                                         "unit": config.RADIUS_UNITS},
                                              "pageParameter": {"page": page_number, "size": page_size}})
                dd = self.query_post_query(query_parameter=query_parameter)
            else:
                more_pages = False
        onts = {'guids': o_guids, 'IDs': o_ids, 'lat_lons': o_these_lat_lons, 'states': o_array_states}
        circuits = {'IDs': c_ids, 'lat_lons': c_these_lat_lons, 'states': c_array_states}
        transformers = {'IDs': x_ids, 'lat_lons': x_these_lat_lons, 'states': x_array_states}
        return onts, circuits, transformers

    def query_waypoints_by_circuit_a1(self, circuit, utility):
        self.status = 'Normal'
        dd = self.utilities_get_utilities_circuits_circuit_id(circuit_id=circuit,
                                                             company=utility,  p=0, s=100)
        lat_lon_array = []
        for i, item in enumerate(dd['eonUtilityEntries']):
            lat_lon_array.append([item['latitude'], item['longitude']])
        return lat_lon_array

    def query_circuits_by_utility_a2(self, circuit, utility):
        self.status = 'Normal'
        # http://10.122.116.17:28080/eon360/api/utilities/circuits/CIR000028?company=CETEST&p=0&s=20
        dd = self.utilities_get_utilities_circuits_circuit_id(circuit_id=circuit,
                                                             company=utility,  p=0, s=100)
        lat_lon_array = []
        for i, item in enumerate(dd['eonUtilityEntries']):
            lat_lon_array.append([item['latitude'], item['longitude']])
        return lat_lon_array


import unittest


class TestSequenceFunctions(unittest.TestCase):
    def setUp(self):
        self.eon_api_bridge = EonApiBridge()

    def test_alarm_get_pons_nms_00(self):
        ans = self.eon_api_bridge.alarm_get_pons_nms_00(start_date_time="", end_date_time="",
                                                        sort_by="alarmReceiveTime", ont_serial_number="", p=0, s=20)
        first_serial_number = ans['alarms'][0]['ont_serial_number']
        self.assertEqual(first_serial_number.find('VZTST'), 0)

    def test_alarm_post_pons_nms_01(self):
        test_ont_serial_number = "VZTST000000"
        alarm_document = {"company": "CENEW",
                          "ontSerialNumber": test_ont_serial_number,
                          "alarmID": "HLSTMACHOL1*LET-2*13*0*16",
                          "alarmSeverity": "2",
                          "alarmConditionType": "PWR-LOS",
                          "alarmReceiveTime": 1414830598000,
                          "alarmClearTime": None,
                          "alarmDescription": "ONT Powering Alarm condition detected",
                          "ontAddress": "37 South Stone Avenue, Elmsford, NY, 10523",
                          "latitude": 41.0192091,
                          "longitude": -73.78027}

        ans = self.eon_api_bridge.alarm_post_pons_nms_01(alarm_document=alarm_document)
        test_response = test_ont_serial_number
        response = ans['alarm']['ontSerialNumber']
        self.assertEqual(response, test_response)

    def test_alarm_get_pons_nms_by_id_02(self):
        alarm_id = "16136dd7-dfa2-4e29-a88a-f4d40d65332a"
        ans = self.eon_api_bridge.alarm_get_pons_nms_by_id_02(alarm_id=alarm_id)
        self.assertEqual(ans['alarm']['guid'], alarm_id)

    def test_eligibilities_post_new_eon_10(self):
        eligibility_entry_document = {"ontSerialNumber": "AAAABBBB",
                                      "modelCoefficients": {"values": [1, 2, 3], "order": 3},
                                      "company": "CENEW",
                                      "errorCode": "0",
                                      "longitude": -71.404519,
                                      "latitude": 42.603399,
                                      "alarmID": "ADLNCAZFOL0*LET-2*0*1*2",
                                      "ontAddress": "1 MAIN,ANYTOWN,MA,01234",
                                      "version": 1}
        # "id": "54237e95e4b0ca40dfbe57d3",
        # "guid": "969905a3-6a3f-4c8b-a1bd-0118aca0a65a",
        ans = self.eon_api_bridge.eligibilities_post_eligibilities(eligibility_entry_document=eligibility_entry_document)
        test_response = ""
        self.assertEqual(ans, test_response)

    def test_eligibilities_get_eons_11(self):
        # test_response = {"pageTotalItems": 20,
        #                  "hasNextPage": True,
        #                  "eonEligibilityEntries": [{"id": "54237e96e4b0ca40dfbe57d4",
        #                                             "version": 0,
        #                                             "guid": "b585681a-1eb4-4683-9beb-0e8fa5af0c73",
        #                                             "company": "",
        #                                             "ontSerialNumber": "44572372",
        #                                             "errorCode": "0",
        #                                             "alarmID": "ADLNCAXFOL0*LET-3*1*1*3",
        #                                             "ontAddress": "10 BURNHAM,METHUEN,MA,01844",
        #                                             "modelCoefficients": None,
        #                                             "latitude": 42.203399,
        #                                             "longitude": -71.304519,
        #                                             "createdAtTimestamp": 1411612310495,
        #                                             "lastModifiedAtTimestamp": 1411612310495},
        #                                            {"id": "5440ee55e4b08fb2ca87be9d",
        #                                             "version": 0,
        #                                             "guid": "ecb4931d-a4e2-44e8-bc67-d1fe9043dee9",
        #                                             "company": "",
        #                                             "ontSerialNumber": "44572374",
        #                                             "errorCode": "0",
        #                                             "alarmID": "ADLNCAXFOL0*LET-3*1*1*3",
        #                                             "ontAddress": "10 BURNHAM,METHUEN,MA,01844",
        #                                             "modelCoefficients": None,
        #                                             "latitude": 42.203399,
        #                                             "longitude": -71.304519,
        #                                             "createdAtTimestamp": 1413541460941,
        #                                             "lastModifiedAtTimestamp": 1413541460941},
        #                                            {"id": "544819a6e4b0bd84ac2d67c0",
        #                                             "version": 0,
        #                                             "guid": "d42ea057-31f2-4da6-bfdd-35fe2b328367",
        #                                             "company": "",
        #                                             "ontSerialNumber": "VZTST44540108",
        #                                             "errorCode": "0",
        #                                             "alarmID": "HLSTMACHOL0*LET-3*14*1*28",
        #                                             "ontAddress": "4 Caralex Lane, Goshen, NY, 10924",
        #                                             "modelCoefficients": None,
        #                                             "latitude": 41.38052,
        #                                             "longitude": -74.373514,
        #                                             "createdAtTimestamp": 1414011301894,
        #                                             "lastModifiedAtTimestamp": 1414011301894},
        #                                            {"id": "544819a6e4b0bd84ac2d67c1",
        #                                             "version": 0,
        #                                             "guid": "ac2a3f76-d04e-489d-9b72-b9f8acb720ea",
        #                                             "company": "",
        #                                             "ontSerialNumber": "VZTST44600033",
        #                                             "errorCode": "0",
        #                                             "alarmID": "HLSTMACHOL0*LET-2*12*0*5",
        #                                             "ontAddress": "4 John Doney Road, Goshen, NY, 10924",
        #                                             "modelCoefficients": None,
        #                                             "latitude": 41.369708,
        #                                             "longitude": -74.431081,
        #                                             "createdAtTimestamp": 1414011302446,
        #                                             "lastModifiedAtTimestamp": 1414011302446},
        #                                            {"id": "544819a6e4b0bd84ac2d67c2",
        #                                             "version": 0,
        #                                             "guid": "16ab54c5-8a10-4739-acdd-04d3811492ab",
        #                                             "company": "",
        #                                             "ontSerialNumber": "VZTST44610022",
        #                                             "errorCode": "0",
        #                                             "alarmID": "HLSTMACHOL1*LET-3*10*0*3",
        #                                             "ontAddress": "3 Swamp Farm Road, Warwick, NY, 10990",
        #                                             "modelCoefficients": None,
        #                                             "latitude": 41.264373,
        #                                             "longitude": -74.458108,
        #                                             "createdAtTimestamp": 1414011302454,
        #                                             "lastModifiedAtTimestamp": 1414011302454},
        #                                            {"id": "544819a6e4b0bd84ac2d67c3",
        #                                             "version": 0,
        #                                             "guid": "be253112-019e-452e-b3aa-e72675444031",
        #                                             "company": "",
        #                                             "ontSerialNumber": "VZTST44610068",
        #                                             "errorCode": "0",
        #                                             "alarmID": "HLSTMACHOL0*LET-2*14*0*13",
        #                                             "ontAddress": "3 Laguardia Road, Chester, NY, 10918",
        #                                             "modelCoefficients": None,
        #                                             "latitude": 41.340837,
        #                                             "longitude": -74.251892,
        #                                             "createdAtTimestamp": 1414011302461,
        #                                             "lastModifiedAtTimestamp": 1414011302461},
        #                                            {"id": "544819a6e4b0bd84ac2d67c4",
        #                                             "version": 0,
        #                                             "guid": "e889cc08-461c-4b35-aa92-4202ce262306",
        #                                             "company": "",
        #                                             "ontSerialNumber": "VZTST44630064",
        #                                             "errorCode": "0",
        #                                             "alarmID": "HLSTMACHOL1*LET-4*12*0*9",
        #                                             "ontAddress": "5 Heidi Lane, Chester, NY, 10918",
        #                                             "modelCoefficients": None,
        #                                             "latitude": 41.347123,
        #                                             "longitude": -74.215676,
        #                                             "createdAtTimestamp": 1414011302465,
        #                                             "lastModifiedAtTimestamp": 1414011302465},
        #                                            {"id": "544819a6e4b0bd84ac2d67c5",
        #                                             "version": 0,
        #                                             "guid": "3af71123-2b47-4698-9522-22f24e0e5e46",
        #                                             "company": "",
        #                                             "ontSerialNumber": "VZTST44650057",
        #                                             "errorCode": "0",
        #                                             "alarmID": "HLSTMACHOL0*LET-4*11*0*1",
        #                                             "ontAddress": "5 7 Oaks Road, Harriman, NY, 10926",
        #                                             "modelCoefficients": None,
        #                                             "latitude": 41.262281,
        #                                             "longitude": -74.172703,
        #                                             "createdAtTimestamp": 1414011302473,
        #                                             "lastModifiedAtTimestamp": 1414011302473},
        #                                            {"id": "544819a6e4b0bd84ac2d67c6",
        #                                             "version": 0,
        #                                             "guid": "07b61419-28cb-460f-bce6-5c88026146cb",
        #                                             "company": "",
        #                                             "ontSerialNumber": "VZTST44660092",
        #                                             "errorCode": "0",
        #                                             "alarmID": "HLSTMACHOL1*LET-3*11*0*12",
        #                                             "ontAddress": "5 Anderson Avenue, Ringwood, NY, 07456",
        #                                             "modelCoefficients": None,
        #                                             "latitude": 41.11597,
        #                                             "longitude": -74.306486,
        #                                             "createdAtTimestamp": 1414011302482,
        #                                             "lastModifiedAtTimestamp": 1414011302482},
        #                                            {"id": "544819a6e4b0bd84ac2d67c7",
        #                                             "version": 0,
        #                                             "guid": "761125c1-fefa-4d8f-ad51-2dcf3cc2f0fc",
        #                                             "company": "",
        #                                             "ontSerialNumber": "VZTST44670086",
        #                                             "errorCode": "0",
        #                                             "alarmID": "HLSTMACHOL0*LET-4*7*1*16",
        #                                             "ontAddress": "2 Skahen Drive, Tomkins Cove, NY, 10986",
        #                                             "modelCoefficients": None,
        #                                             "latitude": 41.245019,
        #                                             "longitude": -74.035405,
        #                                             "createdAtTimestamp": 1414011302496,
        #                                             "lastModifiedAtTimestamp": 1414011302496},
        #                                            {"id": "544819a6e4b0bd84ac2d67c8",
        #                                             "version": 0,
        #                                             "guid": "faeb1632-345a-4581-9480-905b29a6bc87",
        #                                             "company": "",
        #                                             "ontSerialNumber": "VZTST44670089",
        #                                             "errorCode": "0",
        #                                             "alarmID": "HLSTMACHOL0*LET-3*11*1*26",
        #                                             "ontAddress": "5 Elm Avenue, Tomkins Cove, NY, 10986",
        #                                             "modelCoefficients": None,
        #                                             "latitude": 41.220824,
        #                                             "longitude": -74.005946,
        #                                             "createdAtTimestamp": 1414011302516,
        #                                             "lastModifiedAtTimestamp": 1414011302516},
        #                                            {"id": "544819a6e4b0bd84ac2d67c9",
        #                                             "version": 0,
        #                                             "guid": "2f3816aa-1eb8-4359-87d6-6f7812ac6eb3",
        #                                             "company": "",
        #                                             "ontSerialNumber": "VZTST44670095",
        #                                             "errorCode": "0",
        #                                             "alarmID": "HLSTMACHOL0*LET-2*8*1*3",
        #                                             "ontAddress": "2 Co Road 109, West Haverstraw, NY, 10993",
        #                                             "modelCoefficients": None,
        #                                             "latitude": 41.181787,
        #                                             "longitude": -73.993243,
        #                                             "createdAtTimestamp": 1414011302529,
        #                                             "lastModifiedAtTimestamp": 1414011302529},
        #                                            {"id": "544819a6e4b0bd84ac2d67ca",
        #                                             "version": 0,
        #                                             "guid": "625456de-5f3b-4a8c-a853-5fa5638f41f0",
        #                                             "company": "",
        #                                             "ontSerialNumber": "VZTST44670096",
        #                                             "errorCode": "0",
        #                                             "alarmID": "HLSTMACHOL0*LET-4*10*0*21",
        #                                             "ontAddress": "2 Bowline Plant Road, Haverstraw, NY, 10927",
        #                                             "modelCoefficients": None,
        #                                             "latitude": 41.191141,
        #                                             "longitude": -73.906757,
        #                                             "createdAtTimestamp": 1414011302539,
        #                                             "lastModifiedAtTimestamp": 1414011302539},
        #                                            {"id": "544819a6e4b0bd84ac2d67cb",
        #                                             "version": 0,
        #                                             "guid": "a29796aa-660f-49be-9c64-c1ba036d9e62",
        #                                             "company": "",
        #                                             "ontSerialNumber": "VZTST44710059",
        #                                             "errorCode": "0",
        #                                             "alarmID": "HLSTMACHOL1*LET-3*1*0*16",
        #                                             "ontAddress": "2 Don Bosco Lane, Stony Point, NY, 10980",
        #                                             "modelCoefficients": None,
        #                                             "latitude": 41.25711,
        #                                             "longitude": -73.981622,
        #                                             "createdAtTimestamp": 1414011302543,
        #                                             "lastModifiedAtTimestamp": 1414011302543},
        #                                            {"id": "544819a6e4b0bd84ac2d67cc",
        #                                             "version": 0,
        #                                             "guid": "d0e50623-9f92-4f99-bb98-4d132ff88198",
        #                                             "company": "",
        #                                             "ontSerialNumber": "VZTST44720082",
        #                                             "errorCode": "0",
        #                                             "alarmID": "HLSTMACHOL0*LET-2*9*0*22",
        #                                             "ontAddress": "2 Ackerman Place, Nyack, NY, 10960",
        #                                             "modelCoefficients": None,
        #                                             "latitude": 41.126451,
        #                                             "longitude": -73.88973,
        #                                             "createdAtTimestamp": 1414011302553,
        #                                             "lastModifiedAtTimestamp": 1414011302553},
        #                                            {"id": "544819a6e4b0bd84ac2d67cd",
        #                                             "version": 0,
        #                                             "guid": "fe7ddf52-130c-4b76-89d5-ed7c7e221d46",
        #                                             "company": "",
        #                                             "ontSerialNumber": "VZTST44730044",
        #                                             "errorCode": "0",
        #                                             "alarmID": "HLSTMACHOL0*LET-2*7*1*19",
        #                                             "ontAddress": "5 Kings Drive, Tuxedo Park, NY, 10987",
        #                                             "modelCoefficients": None,
        #                                             "latitude": 41.148555,
        #                                             "longitude": -74.292973,
        #                                             "createdAtTimestamp": 1414011302560,
        #                                             "lastModifiedAtTimestamp": 1414011302560},
        #                                            {"id": "544819a6e4b0bd84ac2d67ce",
        #                                             "version": 0,
        #                                             "guid": "0c06098e-53fc-4f0b-b5db-d2c5d14b636b",
        #                                             "company": "",
        #                                             "ontSerialNumber": "VZTST44740066",
        #                                             "errorCode": "0",
        #                                             "alarmID": "HLSTMACHOL1*LET-3*3*0*15",
        #                                             "ontAddress": "3 Kings Drive, Tuxedo Park, NY, 10987",
        #                                             "modelCoefficients": None,
        #                                             "latitude": 41.141458,
        #                                             "longitude": -74.236486,
        #                                             "createdAtTimestamp": 1414011302566,
        #                                             "lastModifiedAtTimestamp": 1414011302566},
        #                                            {"id": "544819a6e4b0bd84ac2d67cf",
        #                                             "version": 0,
        #                                             "guid": "7306903f-1825-4bbe-a551-a6d770e611d9",
        #                                             "company": "",
        #                                             "ontSerialNumber": "VZTST44740070",
        #                                             "errorCode": "0",
        #                                             "alarmID": "HLSTMACHOL1*LET-2*14*0*22",
        #                                             "ontAddress": "3 Mansion Road, Ringwood, NY, 07456",
        #                                             "modelCoefficients": None,
        #                                             "latitude": 41.151939,
        #                                             "longitude": -74.225405,
        #                                             "createdAtTimestamp": 1414011302572,
        #                                             "lastModifiedAtTimestamp": 1414011302572},
        #                                            {"id": "544819a6e4b0bd84ac2d67d0",
        #                                             "version": 0,
        #                                             "guid": "7c9f5565-4570-4bfc-8b5f-5f7f8f87738d",
        #                                             "company": "",
        #                                             "ontSerialNumber": "VZTST44780063",
        #                                             "errorCode": "0",
        #                                             "alarmID": "HLSTMACHOL1*LET-4*6*1*10",
        #                                             "ontAddress": "4 Sergeant Ahlmeyer Drive, West Nyack, NY, 10994",
        #                                             "modelCoefficients": None,
        #                                             "latitude": 41.069835,
        #                                             "longitude": -73.948919,
        #                                             "createdAtTimestamp": 1414011302577,
        #                                             "lastModifiedAtTimestamp": 1414011302577},
        #                                            {"id": "544819a6e4b0bd84ac2d67d1",
        #                                             "version": 0,
        #                                             "guid": "32e93093-e1bd-42e3-b14b-de0e631c5c63",
        #                                             "company": "",
        #                                             "ontSerialNumber": "VZTST45530191",
        #                                             "errorCode": "0",
        #                                             "alarmID": "HLSTMACHOL1*LET-2*3*0*10",
        #                                             "ontAddress": "4 Dickerson Road, Cortlandt, NY, 10567",
        #                                             "modelCoefficients": None,
        #                                             "latitude": 41.285019,
        #                                             "longitude": -73.875405,
        #                                             "createdAtTimestamp": 1414011302612,
        #                                             "lastModifiedAtTimestamp": 1414011302612}],
        #                  "page": 0,
        #                  "start": 0,
        #                  "pageSize": 20,
        #                  "hasPreviousPage": False,
        #                  "totalPages": 53845,
        #                  "end": 1416189382905}
        ans = self.eon_api_bridge.eligibilities_get_eligibilities(start_date_time="", end_date_time="", p=0, s=20)
        self.assertEqual(len(ans['eonEligibilityEntries']), 20)

    def test_eligibilities_get_eon_by_id_12(self):
        eligibility_entry_id = "969905a3-6a3f-4c8b-a1bd-0118aca0a65a"
        ans = self.eon_api_bridge.eligibilities_get_eligibility_entry_id(eligibility_entry_id=eligibility_entry_id)
        test_response = {'id': '969905a3-6a3f-4c8b-a1bd-0118aca0a65a',
                         'eligibilityEntry': {'ontSerialNumber': '44572372',
                                              'lastModifiedAtTimestamp': 1416181551308L,
                                              'createdAtTimestamp': 1411612309218L,
                                              'ontAddress': '10 BURNHAM,METHUEN,MA,01844',
                                              'modelCoefficients': {'values': [1.5, 1.6, 99.9],
                                                                    'order': 3},
                                              'company': '',
                                              'longitude': -71.304519,
                                              'alarmID': 'ADLNCAXFOL0*LET-3*1*1*3',
                                              'errorCode': '0', 'version': 3,
                                              'latitude': 42.203399,
                                              'guid': '969905a3-6a3f-4c8b-a1bd-0118aca0a65a',
                                              'id': '54237e95e4b0ca40dfbe57d3'}}

        self.assertItemsEqual(ans, test_response)

    def test_eligibilities_put_eon_coefficient_13(self):
        coefficients = [1.5, 1.6, 99.9]
        model_coefficients = {"values": coefficients, "order": len(coefficients)}
        # test_response = {"id": "969905a3-6a3f-4c8b-a1bd-0118aca0a65a",
        #                  "eligibilityEntry": {"id": "54237e95e4b0ca40dfbe57d3",
        #                                       "version": 1,
        #                                       "guid": "969905a3-6a3f-4c8b-a1bd-0118aca0a65a",
        #                                       "company": "",
        #                                       "ontSerialNumber": "44572372",
        #                                       "errorCode": "0",
        #                                       "alarmID": "ADLNCAXFOL0*LET-3*1*1*3",
        #                                       "ontAddress": "10 BURNHAM,METHUEN,MA,01844",
        #                                       "modelCoefficients": {
        #                                           "order": 3,
        #                                           "values": [1.5, 1.6, 99.9]},
        #                                       "latitude": 42.203399,
        #                                       "longitude": -71.304519,
        #                                       "createdAtTimestamp": 1411612309218,
        #                                       "lastModifiedAtTimestamp": 1415591867730}}
        eligibility_entry_id = "969905a3-6a3f-4c8b-a1bd-0118aca0a65a"
        ans = self.eon_api_bridge.eligibilities_put_eligibility_entry_id(eligibility_entry_id=eligibility_entry_id,
                                                                       model_coefficients=model_coefficients)

        self.assertEqual(ans['eligibilityEntry']['modelCoefficients']['values'], coefficients)

    def test_outages_get_outage_utility_20(self):
        """
        see email from Yong on Thu 10/16/2014 6:46 AM
        """
        # return_response = {
        #     "pageTotalItems": 1,
        #     "hasNextPage": False,
        #     "range": [
        #         {
        #             "x": -71.304519,  # //minLongitude
        #             "y": 42.203399  # //minLatitude
        #         },
        #         {
        #             "x": -71.304519,  # //maxLongitude
        #             "y": 42.203399  # //maxLatitude
        #         }
        #     ],
        #     "page": 0,
        #     "start": 0,
        #     "pageSize": 20,
        #     "hasPreviousPage": False,
        #     "outages": [
        #         {
        #             "id": "543d20aae4b0913c5d6bf2f9",
        #             "version": 0,
        #             "guid": "c32b60e5-d22e-4389-8a93-6faa006d2ad8",
        #             "company": "nationalgrid",
        #             "utilityID": "CIR123456",
        #             "deviceType": "circuit",
        #             "powerStatus": "loss",
        #             "timeOfEvent": 1410781218390,
        #             "deviceAddressString": "1 ABBOTT CT RGHT, Woburn , MA, 01801",
        #             "deviceState": True,
        #             "latitude": 42.203399,
        #             "longitude": -71.304519,
        #             "createdAtTimestamp": 1413292202362,
        #             "lastModifiedAtTimestamp": 1413292202362
        #         }
        #     ],
        #     "totalPages": 1,
        #     "end": 1413292239644
        # }

        ans = self.eon_api_bridge.outages_get_outages(start_date_time="", end_date_time="",
                                                                sort_by="timeOfEvent",
                                                                current_outage_only=True, company="CETEST", p=0, s=20)
        self.assertItemsEqual(ans['outages'][0]['company'], 'CETEST')

    def test_outages_post_outage_utility_new_21(self):
        #        utility_outage_document={
        #                            "powerStatus": "loss",
        #                            "timeOfEvent": 1410781218390,
        #                            "utilityID": str(waypoint['guid']), # this should be the guid of the circuit ID
        #                            "deviceType": "circuit",
        #                            "company": "CETEST",
        #                            "longitude": -71.304519,
        #                            "latitude": 42.203399,
        #                            "deviceState" : False # set this to False so it picked up by the outage API
        #                        }

        utility_test_outage = {
            "powerStatus": "loss",
            "timeOfEvent": 1410781218390,
            "utilityID": "CIR000028",
            "deviceType": "circuit",
            "company": "CETEST",
            "longitude": -73.988919,
            "latitude": 41.069835,
            "deviceState": False  # Set to False to make it a real outage
        }
        test_results = {
            "outage": {
                "company": "CETEST",
                "createdAtTimestamp": 1416182558338,
                "currentState": True,
                "deviceAddressString": None,
                "deviceState": False,
                "deviceType": "circuit",
                "guid": "74c08b52-0cd5-48a1-912c-8b965c5c0f4f",
                "id": "54693b1ee4b0b284cfd8dfe9",
                "lastModifiedAtTimestamp": 1416182558338,
                "latitude": 41.069835,
                "longitude": -73.988919,
                "powerStatus": "loss",
                "timeOfEvent": 1410781218390,
                "utilityID": "CIR000028",
                "version": 0
            }
        }

        ans = self.eon_api_bridge.outages_post_outages(utility_outage_document=utility_test_outage)
        # self.assertEqual(ans, test_results)
        self.assertItemsEqual(ans, test_results)

    def test_outages_get_outage_utility_by_id_22(self):
        outage_id = "54693b1ee4b0b284cfd8dfe9"
        ans = self.eon_api_bridge.outages_get_outage_outage_id(outage_id=outage_id)
        test_response = {u'outage': {
            u'lastModifiedAtTimestamp': 1416183324469L,
            u'powerStatus': u'loss',
            u'longitude': -73.988919,
            u'createdAtTimestamp': 1416182558338L,
            u'timeOfEvent': 1410781218390L,
            u'company': u'CETEST',
            u'utilityID': u'CIR000028',
            u'version': 3,
            u'deviceType': u'circuit',
            u'currentState': False,
            u'latitude': 41.069835,
            u'deviceAddressString': None,
            u'guid': u'74c08b52-0cd5-48a1-912c-8b965c5c0f4f',
            u'id': u'54693b1ee4b0b284cfd8dfe9',
            u'deviceState': False},
            u'id': u'54693b1ee4b0b284cfd8dfe9'}
        self.assertItemsEqual(ans, test_response)

    def test_outages_put_outage_utility_update_23(self):

        utility_outage_document = {"deviceState": False}
        outage_id = "54693b1ee4b0b284cfd8dfe9"  # This is id returned in the test_outages_post_outage_utility_new test
        ans = self.eon_api_bridge.outages_put_outage_outage_id(outage_id=outage_id,
                                                                       utility_outage_document=utility_outage_document)
        self.assertItemsEqual({"deviceState": ans['outage']['deviceState']}, utility_outage_document)

    def test_query_post_eon_data_30(self):
        query_parameter = {"itemType": "ELIGIBILITY",  # // ALL, ELIGIBILITY, ALARM, UTILITY
                           "circle": {
                               "longitude": -71.304519,
                               "latitude": 42.203399,
                               "radius": 1.0,
                               "unit": "MILES"},
                           "pageParameter": {
                               "page": 0,
                               "size": 20
                           }}
        test_result = [u'ontSerialNumber', u'lastModifiedAtTimestamp',
                       u'createdAtTimestamp', u'ontAddress',
                       u'modelCoefficients', u'company',
                       u'longitude', u'alarmID',
                       u'errorCode', u'version',
                       u'latitude', u'guid', u'id']
        ans = self.eon_api_bridge.query_post_query(query_parameter=query_parameter)
        self.assertEqual(ans['eligibility']['dataItems'][0].keys(), test_result)

    def test_query_post_alarm_data_31(self):
        """
        New on 11/14/2014
        """
        # test_response = {
        #     "pageTotalItems": 4,
        #     "hasNextPage": False,
        #     "page": 0,
        #     "ontSerialNumbers": [
        #         "VZTST44510093",
        #         "VZTST44510103"
        #     ],
        #     "pageSize": 20,
        #     "hasPreviousPage": False,
        #     "totalPages": 1,
        #     "alarms": [
        #         {
        #             "id": "545aa5e7e4b01dabc5568f95",
        #             "version": 0,
        #             "guid": "a985a2f2-3b2d-4219-91a4-78fca9eb3a24",
        #             "company": "",
        #             "ontSerialNumber": "VZTST44510093",
        #             "alarmID": "HLSTMACHOL1*LET-1*2*0*3",
        #             "alarmSeverity": "2",
        #             "alarmConditionType": "PWR-LOS",
        #             "alarmReceiveTime": 1415237604000,
        #             "alarmClearTime": None,
        #             "alarmDescription": "ONT Powering Alarm condition detected",
        #             "ontAddress": "26 Henderson Drive, Circleville, NY, 10919",
        #             "latitude": 41.524081,
        #             "longitude": -74.396216,
        #             "createdAtTimestamp": 1415226855429,
        #             "lastModifiedAtTimestamp": 1415226855429
        #         },
        #         {
        #             "id": "545aa5e7e4b01dabc5568f94",
        #             "version": 0,
        #             "guid": "de6e1682-1996-4f30-bdd4-18b12dce0dba",
        #             "company": "",
        #             "ontSerialNumber": "VZTST44510103",
        #             "alarmID": "HLSTMACHOL0*LET-1*8*0*22",
        #             "alarmSeverity": "2",
        #             "alarmConditionType": "PWR-LOS",
        #             "alarmReceiveTime": 1415237604000,
        #             "alarmClearTime": None,
        #             "alarmDescription": "ONT Powering Alarm condition detected",
        #             "ontAddress": "87 Cemetery Road, Middletown, NY, 10940",
        #             "latitude": 41.393587,
        #             "longitude": -74.401892,
        #             "createdAtTimestamp": 1415226855424,
        #             "lastModifiedAtTimestamp": 1415226855424
        #         },
        #         {
        #             "id": "545aa23be4b01dabc5568f8a",
        #             "version": 0,
        #             "guid": "7c77c82c-dd06-48b6-b2de-912635d8853b",
        #             "company": "",
        #             "ontSerialNumber": "VZTST44510093",
        #             "alarmID": "HLSTMACHOL1*LET-1*2*0*3",
        #             "alarmSeverity": "2",
        #             "alarmConditionType": "PWR-LOS",
        #             "alarmReceiveTime": 1415236670000,
        #             "alarmClearTime": None,
        #             "alarmDescription": "ONT Powering Alarm condition detected",
        #             "ontAddress": "26 Henderson Drive, Circleville, NY, 10919",
        #             "latitude": 41.524081,
        #             "longitude": -74.396216,
        #             "createdAtTimestamp": 1415225915422,
        #             "lastModifiedAtTimestamp": 1415225915422
        #         },
        #         {
        #             "id": "545aa23be4b01dabc5568f89",
        #             "version": 0,
        #             "guid": "4c80a1f6-8456-49db-84ae-a35ba07096da",
        #             "company": "",
        #             "ontSerialNumber": "VZTST44510103",
        #             "alarmID": "HLSTMACHOL0*LET-1*8*0*22",
        #             "alarmSeverity": "2",
        #             "alarmConditionType": "PWR-LOS",
        #             "alarmReceiveTime": 1415236670000,
        #             "alarmClearTime": None,
        #             "alarmDescription": "ONT Powering Alarm condition detected",
        #             "ontAddress": "87 Cemetery Road, Middletown, NY, 10940",
        #             "latitude": 41.393587,
        #             "longitude": -74.401892,
        #             "createdAtTimestamp": 1415225915417,
        #             "lastModifiedAtTimestamp": 1415225915417
        #         }
        #     ]
        # }
        test_alarms = ["VZTST44510093", "VZTST44510103"]
        ans = self.eon_api_bridge.query_post_query_alarms(alarm_ids=test_alarms, p=0, s=20)
        self.assertEqual(ans['ontSerialNumbers'], test_alarms)

    def test_query_post_utility_data_32(self):
        # test_response = {"states": [{"id": "546035bde4b0f31984ced710",
        #                              "version": 0,
        #                              "guid": "61af9072-3d67-47bc-ae02-f3ddde6f5219",
        #                              "company": "CETEST",
        #                              "utilityID": "CIR000010",
        #                              "deviceType": "circuit",
        #                              "powerStatus": "loss",
        #                              "timeOfEvent": 1410781218390,
        #                              "deviceAddressString": "1 ABBOTT CT RGHT, Woburn , MA, 01801",
        #                              "deviceState": False,
        #                              "currentState": True,
        #                              "latitude": 42.203399,
        #                              "longitude": -71.304519,
        #                              "createdAtTimestamp": 1415591357528,
        #                              "lastModifiedAtTimestamp": 1415591357528},
        #                             {"id": "5460357ce4b0f31984ced70f",
        #                              "version": 0,
        #                              "guid": "8d078301-2319-46e7-8eff-6beaae48a40b",
        #                              "company": "CETEST",
        #                              "utilityID": "CIR000004",
        #                              "deviceType": "circuit",
        #                              "powerStatus": "loss",
        #                              "timeOfEvent": 1410781218390,
        #                              "deviceAddressString": "1 ABBOTT CT RGHT, Woburn , MA, 01801",
        #                              "deviceState": False,
        #                              "currentState": True,
        #                              "latitude": 42.203399,
        #                              "longitude": -71.304519,
        #                              "createdAtTimestamp": 1415591292773,
        #                              "lastModifiedAtTimestamp": 1415591292773}],
        #                  "utilities": [{"id": "544550a4e4b0e4a25a623ea5",
        #                                 "version": 0,
        #                                 "guid": "1a46cc4c-d868-4fe3-a7a7-c434adcf67fe",
        #                                 "company": "CETEST",
        #                                 "serviceAddress": "1 John Doney Road, Goshen, NY, 10924",
        #                                 "errorCode": "0",
        #                                 "circuitID": "CIR000010",
        #                                 "transformerID": "TR0000100013",
        #                                 "eligibilityList": None,
        #                                 "downStreamItemID": None,
        #                                 "upStreamItemID": None,
        #                                 "latitude": 41.369708,
        #                                 "longitude": -74.391081,
        #                                 "createdAtTimestamp": 1413828772403,
        #                                 "lastModifiedAtTimestamp": 1413828772403},
        #                                {"id": "544550a4e4b0e4a25a623ea3",
        #                                 "version": 0,
        #                                 "guid": "2aaea56e-7499-4026-b052-9ca0438e3106",
        #                                 "company": "CETEST",
        #                                 "serviceAddress": "1 Caralex Lane, Goshen, NY, 10924",
        #                                 "errorCode": "0",
        #                                 "circuitID": "CIR000004",
        #                                 "transformerID": "TR0000040094",
        #                                 "eligibilityList": None,
        #                                 "downStreamItemID": None,
        #                                 "upStreamItemID": None,
        #                                 "latitude": 41.41052,
        #                                 "longitude": -74.363514,
        #                                 "createdAtTimestamp": 1413828772382,
        #                                 "lastModifiedAtTimestamp": 1413828772382}]}
        utility_ids = ["2aaea56e-7499-4026-b052-9ca0438e3106", "1a46cc4c-d868-4fe3-a7a7-c434adcf67fe"]
        ans = self.eon_api_bridge.query_post_query_utilities(utility_ids=utility_ids)

        response = [ans['utilities'][0]['guid'], ans['utilities'][1]['guid']]
        self.assertItemsEqual(response, utility_ids)

    def test_tools_get_outage_region_50(self):
        company = 'CETEST'
        ans = self.eon_api_bridge.tools_get_outage_region(start_date_time="", end_date_time="", company=company)
        test_response = {u'region': {u'maxLatitude': 42.203399,
                                     u'minLongitude': -74.614865,
                                     u'maxLongitude': -71.304519,
                                     u'minLatitude': 41.069835}}
        self.assertItemsEqual(ans, test_response)

    def test_utilities_get_eon_utility_entries_60(self):
        company = 'CETEST'
        ans = self.eon_api_bridge.utilities_get_utilities(start_date_time="",
                                                                       end_date_time="", company=company, p=0, s=20)
        self.assertEqual(ans['company'], company)

    def test_utilities_post_eon_utility_entry_61(self):
        utility_document = {"powerStatus": "loss",
                            "timeOfEvent": 1410781218390,
                            "utilityID": "CIR123456",
                            "deviceType": "circuit",
                            "company": "",
                            "deviceAddressString": "1 ABBOTT CT RGHT, Woburn , MA, 01801",
                            "longitude": -71.304519,
                            "latitude": 42.203399}
        test_response = ""
        ans = self.eon_api_bridge.utilities_post_utilities(utility_document=utility_document)
        self.assertEqual(ans, test_response)

    def test_utilities_get_eon_utility_entries_61(self):
        company = 'CETEST'
        ans = self.eon_api_bridge.utilities_get_utilities(start_date_time="", end_date_time="", company=company, p=0, s=20)
        self.assertEqual(ans['company'], company)

    def test_utilities_get_eon_utility_by_id_62(self):
        utility_id = "544550a4e4b0e4a25a623ea3"
        # test_response = {"utility": {"id": "544550a4e4b0e4a25a623ea3",
        #                              "version": 2,
        #                              "guid": "2aaea56e-7499-4026-b052-9ca0438e3106",
        #                              "company": "CETEST",
        #                              "serviceAddress": "1 Caralex Lane, Goshen, NY, 10924",
        #                              "errorCode": "0",
        #                              "circuitID": "CIR000004",
        #                              "transformerID": "TR0000040094",
        #                              "eligibilityList": [{"id": "54237e96e4b0ca40dfbe57d4",
        #                                                   "version": 0,
        #                                                   "guid": "b585681a-1eb4-4683-9beb-0e8fa5af0c73",
        #                                                   "company": "",
        #                                                   "ontSerialNumber": "44572372",
        #                                                   "errorCode": "0",
        #                                                   "alarmID": "ADLNCAXFOL0*LET-3*1*1*3",
        #                                                   "ontAddress": "10 BURNHAM,METHUEN,MA,01844",
        #                                                   "modelCoefficients": None,
        #                                                   "latitude": 42.203399,
        #                                                   "longitude": -71.304519,
        #                                                   "createdAtTimestamp": 1411612310495,
        #                                                   "lastModifiedAtTimestamp": 1411612310495},
        #                                                  {"id": "5440ee55e4b08fb2ca87be9d",
        #                                                   "version": 0,
        #                                                   "guid": "ecb4931d-a4e2-44e8-bc67-d1fe9043dee9",
        #                                                   "company": "",
        #                                                   "ontSerialNumber": "44572374",
        #                                                   "errorCode": "0",
        #                                                   "alarmID": "ADLNCAXFOL0*LET-3*1*1*3",
        #                                                   "ontAddress": "10 BURNHAM,METHUEN,MA,01844",
        #                                                   "modelCoefficients": None,
        #                                                   "latitude": 42.203399,
        #                                                   "longitude": -71.304519,
        #                                                   "createdAtTimestamp": 1413541460941,
        #                                                   "lastModifiedAtTimestamp": 1413541460941}],
        #                              "downStreamItemID": "1a46cc4c-d868-4fe3-a7a7-c434adcf67fe",
        #                              "upStreamItemID": None,
        #                              "latitude": 41.41052,
        #                              "longitude": -74.363514,
        #                              "createdAtTimestamp": 1413828772382,
        #                              "lastModifiedAtTimestamp": 1415789981731}}
        ans = self.eon_api_bridge.utilities_get_utilities_utility_id(utility_id=utility_id)
        self.assertEqual(ans['id'], utility_id)

    def test_utilities_post_eon_utility_downstream_63(self):
        # test_response = {"utility": {"id": "544550a4e4b0e4a25a623ea3",
        #                              "version": 1,
        #                              "guid": "2aaea56e-7499-4026-b052-9ca0438e3106",
        #                              "company": "CETEST",
        #                              "serviceAddress": "1 Caralex Lane, Goshen, NY, 10924",
        #                              "errorCode": "0",
        #                              "circuitID": "CIR000004",
        #                              "transformerID": "TR0000040094",
        #                              "eligibilityList": None,
        #                              "downStreamItemID": "1a46cc4c-d868-4fe3-a7a7-c434adcf67fe",
        #                              "upStreamItemID": None,
        #                              "latitude": 41.41052,
        #                              "longitude": -74.363514,
        #                              "createdAtTimestamp": 1413828772382,
        #                              "lastModifiedAtTimestamp": 1415789589436}}
        guid = "2aaea56e-7499-4026-b052-9ca0438e3106"
        down_stream_id = "1a46cc4c-d868-4fe3-a7a7-c434adcf67fe"
        ans = self.eon_api_bridge.utilities_post_utilities_utility_id_downstream_downstream_id(utility_id=guid,
                                                                           down_stream_id=down_stream_id)
        # self.my_local_logger.info( json.dumps(ans, sort_keys=True, indent=4))
        # The response changes with the new update
        test_response = [guid, down_stream_id]
        self.assertEqual([ans['utility']['guid'], ans['utility']['downStreamItemID']], test_response)

    def test_utilities_post_eon_utility_associated_onts_64(self):
        # test_response = {"utility": {"id": "544550a4e4b0e4a25a623ea3",
        #                              "version": 2,
        #                              "guid": "2aaea56e-7499-4026-b052-9ca0438e3106",
        #                              "company": "CETEST",
        #                              "serviceAddress": "1 Caralex Lane, Goshen, NY, 10924",
        #                              "errorCode": "0",
        #                              "circuitID": "CIR000004",
        #                              "transformerID": "TR0000040094",
        #                              "eligibilityList": [{"id": "54237e96e4b0ca40dfbe57d4",
        #                                                   "version": 0,
        #                                                   "guid": "b585681a-1eb4-4683-9beb-0e8fa5af0c73",
        #                                                   "company": "",
        #                                                   "ontSerialNumber": "44572372",
        #                                                   "errorCode": "0",
        #                                                   "alarmID": "ADLNCAXFOL0*LET-3*1*1*3",
        #                                                   "ontAddress": "10 BURNHAM,METHUEN,MA,01844",
        #                                                   "modelCoefficients": None,
        #                                                   "latitude": 42.203399,
        #                                                   "longitude": -71.304519,
        #                                                   "createdAtTimestamp": 1411612310495,
        #                                                   "lastModifiedAtTimestamp": 1411612310495},
        #                                                  {"id": "5440ee55e4b08fb2ca87be9d",
        #                                                   "version": 0,
        #                                                   "guid": "ecb4931d-a4e2-44e8-bc67-d1fe9043dee9",
        #                                                   "company": "",
        #                                                   "ontSerialNumber": "44572374",
        #                                                   "errorCode": "0",
        #                                                   "alarmID": "ADLNCAXFOL0*LET-3*1*1*3",
        #                                                   "ontAddress": "10 BURNHAM,METHUEN,MA,01844",
        #                                                   "modelCoefficients": None,
        #                                                   "latitude": 42.203399,
        #                                                   "longitude": -71.304519,
        #                                                   "createdAtTimestamp": 1413541460941,
        #                                                   "lastModifiedAtTimestamp": 1413541460941}],
        #                              "downStreamItemID": "1a46cc4c-d868-4fe3-a7a7-c434adcf67fe",
        #                              "upStreamItemID": None,
        #                              "latitude": 41.41052,
        #                              "longitude": -74.363514,
        #                              "createdAtTimestamp": 1413828772382,
        #                              "lastModifiedAtTimestamp": 1415789981731}}
        guid = "2aaea56e-7499-4026-b052-9ca0438e3106"
        eligibility_ids = ["b585681a-1eb4-4683-9beb-0e8fa5af0c73", "ecb4931d-a4e2-44e8-bc67-d1fe9043dee9"]
        ans = self.eon_api_bridge.utilities_post_utilities_utility_id_eligibilities(utility_id=guid,
                                                                                eligibility_ids=eligibility_ids)
        # self.my_local_logger.info( json.dumps(ans, sort_keys=True, indent=4))
        # Just validate that the first 2 IDs are what was specified
        self.assertEqual([ans['utility']['eligibilityList'][0]['guid'],
                          ans['utility']['eligibilityList'][1]['guid']], eligibility_ids)

    def test_utilities_post_eon_utility_upstream_65(self):
        # test_response = {"utility": {"id": "544550a4e4b0e4a25a623ea5",
        #                              "version": 1,
        #                              "guid": "1a46cc4c-d868-4fe3-a7a7-c434adcf67fe",
        #                              "company": "CETEST",
        #                              "serviceAddress": "1 John Doney Road, Goshen, NY, 10924",
        #                              "errorCode": "0",
        #                              "circuitID": "CIR000010",
        #                              "transformerID": "TR0000100013",
        #                              "eligibilityList": None,
        #                              "downStreamItemID": None,
        #                              "upStreamItemID": "2aaea56e-7499-4026-b052-9ca0438e3106",
        #                              "latitude": 41.369708,
        #                              "longitude": -74.391081,
        #                              "createdAtTimestamp": 1413828772403,
        #                              "lastModifiedAtTimestamp": 1415789801364}}
        guid = "1a46cc4c-d868-4fe3-a7a7-c434adcf67fe"
        upstream_id = "2aaea56e-7499-4026-b052-9ca0438e3106"
        test_response = [guid, upstream_id]
        ans = self.eon_api_bridge.utilities_post_utilities_utility_id_upstream_upstream_id(utility_id=guid, upstream_id=upstream_id)
        # self.my_local_logger.info( json.dumps(ans, sort_keys=True, indent=4))
        self.assertEqual([ans['utility']['guid'], ans['utility']['upStreamItemID']], test_response)

    def test_utilities_get_eon_utility_circuit_by_id_66(self):
        circuit_id = 'CIR000028'
        utility = 'CETEST'
        ans = self.eon_api_bridge.utilities_get_utilities_circuits_circuit_id(circuit_id=circuit_id,
                                                                             company=utility,  p=0, s=20)
        test_response = [utility, circuit_id]
        self.assertEqual([ans['company'], ans['circuitID']], test_response)

    def test_utilities_get_eon_utility_transformer_by_id_67(self):
        transformer_id = "TR0000100013"
        company = "CETEST"
        ans = self.eon_api_bridge.utilities_get_transformers_transformer_id(transformer_id=transformer_id,
                                                                                 company=company,  p=0, s=20)
        test_response = {u'pageTotalItems': 1,
                         u'hasPreviousPage': False,
                         u'pageSize': 20,
                         u'company': u'CETEST',
                         u'eonUtilityEntries': [{u'lastModifiedAtTimestamp': 1416179244140L,
                                                 u'circuitID': u'CIR000010',
                                                 u'createdAtTimestamp': 1413828772403L,
                                                 u'company': u'CETEST',
                                                 u'upStreamItemID': u'2aaea56e-7499-4026-b052-9ca0438e3106',
                                                 u'longitude': -74.391081,
                                                 u'errorCode': u'0',
                                                 u'latitude': 41.369708,
                                                 u'downStreamItemID': None,
                                                 u'version': 3,
                                                 u'serviceAddress': u'1 John Doney Road, Goshen, NY, 10924',
                                                 u'eligibilityList': None,
                                                 u'guid': u'1a46cc4c-d868-4fe3-a7a7-c434adcf67fe',
                                                 u'id': u'544550a4e4b0e4a25a623ea5',
                                                 u'transformerID': u'TR0000100013'}],
                         u'totalPages': 1,
                         u'transformerID': u'TR0000100013',
                         u'page': 0,
                         u'hasNextPage': False}
        self.assertItemsEqual(ans, test_response)

    def test_query_eon_area_A0(self):
        lat = 41.069835
        lon = -73.988919
        radius = 1.0
        ans = self.eon_api_bridge.query_eon_area_a0(lat, lon, radius)
        test_response = ['lat_lons', 'states', 'guids', 'IDs']
        self.assertEqual(ans[0].keys(), test_response)

    def test_query_waypoints_by_circuit_A1(self):
        ans = self.eon_api_bridge.query_waypoints_by_circuit_a1(circuit="CIR000028", utility="CETEST")
        # There are 43 waypoints on CIR000028 for utility == CETEST
        test_response = [[41.069835, -73.988919], [41.075158, -74.107297], [41.068061, -74.117027],
                         [41.060963, -74.112162], [41.076933, -74.00027], [41.05564, -74.112162],
                         [40.963371, -73.964595], [41.048542, -74.123514], [41.020152, -73.962973],
                         [41.064512, -74.165676], [40.947402, -73.941892], [41.052091, -74.152703],
                         [41.076933, -74.029459], [40.945627, -73.954865], [40.991762, -73.977568],
                         [40.945627, -73.948378], [40.959823, -73.964595], [41.08403, -74.01],
                         [41.082256, -74.018108], [41.082256, -74.095946], [41.060963, -73.977568],
                         [41.082256, -74.005135], [40.949176, -73.958108], [41.052091, -74.131622],
                         [41.07161, -73.995405], [41.034347, -73.964595], [41.002408, -73.969459],
                         [41.082256, -74.091081], [40.945627, -73.935405], [41.014829, -73.967838],
                         [41.009506, -73.967838], [41.082256, -74.050541], [41.050317, -74.141351],
                         [40.977567, -73.971081], [41.082256, -74.074865], [41.057414, -74.165676],
                         [40.968695, -73.971081], [41.080482, -74.045676], [41.080482, -74.099189],
                         [40.933207, -73.912703], [40.940304, -73.920811], [41.066286, -73.980811],
                         [41.08403, -74.065135]]
        self.assertEqual(ans, test_response)

    def test_query_circuits_by_utility_a2(self):
        ans = self.eon_api_bridge.query_circuits_by_utility_a2(circuit="CIR000028", utility="CETEST")
        # There are 43 waypoints on CIR000028 for utility==CETEST
        test_response = [[41.069835, -73.988919], [41.075158, -74.107297], [41.068061, -74.117027],
                         [41.060963, -74.112162], [41.076933, -74.00027], [41.05564, -74.112162],
                         [40.963371, -73.964595], [41.048542, -74.123514], [41.020152, -73.962973],
                         [41.064512, -74.165676], [40.947402, -73.941892], [41.052091, -74.152703],
                         [41.076933, -74.029459], [40.945627, -73.954865], [40.991762, -73.977568],
                         [40.945627, -73.948378], [40.959823, -73.964595], [41.08403, -74.01],
                         [41.082256, -74.018108], [41.082256, -74.095946], [41.060963, -73.977568],
                         [41.082256, -74.005135], [40.949176, -73.958108], [41.052091, -74.131622],
                         [41.07161, -73.995405], [41.034347, -73.964595], [41.002408, -73.969459],
                         [41.082256, -74.091081], [40.945627, -73.935405], [41.014829, -73.967838],
                         [41.009506, -73.967838], [41.082256, -74.050541], [41.050317, -74.141351],
                         [40.977567, -73.971081], [41.082256, -74.074865], [41.057414, -74.165676],
                         [40.968695, -73.971081], [41.080482, -74.045676], [41.080482, -74.099189],
                         [40.933207, -73.912703], [40.940304, -73.920811], [41.066286, -73.980811],
                         [41.08403, -74.065135]]
        self.assertEqual(ans, test_response)


def suite():
    test_suite = unittest.TestSuite()
    test_suite.addTest(unittest.makeSuite(TestSequenceFunctions))
    return test_suite

if __name__ == '__main__':
    LOG_FORMAT = ('%(levelname)s %(asctime)s %(name)s %(funcName) '
                  '%(lineno)5d:%(message)s')
    my_local_logger = logging.getLogger(__name__)
    my_local_logger.setLevel(logging.INFO)
    my_local_logger.info("Running eon_api_bridge in stand-alone mode")
    os.chdir(config.BASE_DIR)
    my_local_logger.info("Running tests...")
    suiteFew = unittest.TestSuite()
    suiteFew.addTest(TestSequenceFunctions('test_alarm_get_pons_nms_00'))                         # 00 VALIDATED
    suiteFew.addTest(TestSequenceFunctions('test_alarm_post_pons_nms_01'))                        # 01 VALIDATED
    suiteFew.addTest(TestSequenceFunctions('test_alarm_get_pons_nms_by_id_02'))                   # 02 VALIDATED
    # suiteFew.addTest(TestSequenceFunctions('test_eligibilities_post_new_eon_10'))               # 10 NOT VALIDATED
    suiteFew.addTest(TestSequenceFunctions('test_eligibilities_get_eons_11'))                     # 11 VALIDATED
    suiteFew.addTest(TestSequenceFunctions('test_eligibilities_get_eon_by_id_12'))                # 12 VALIDATED
    suiteFew.addTest(TestSequenceFunctions('test_eligibilities_put_eon_coefficient_13'))          # 13 VALIDATED
    suiteFew.addTest(TestSequenceFunctions('test_outages_get_outage_utility_20'))                 # 20 VALIDATED
    suiteFew.addTest(TestSequenceFunctions('test_outages_post_outage_utility_new_21'))            # 21 VALIDATED
    suiteFew.addTest(TestSequenceFunctions('test_outages_get_outage_utility_by_id_22'))           # 22 VALIDATED
    suiteFew.addTest(TestSequenceFunctions('test_outages_put_outage_utility_update_23'))          # 23 VALIDATED
    suiteFew.addTest(TestSequenceFunctions('test_query_post_eon_data_30'))                        # 30 VALIDATED
    suiteFew.addTest(TestSequenceFunctions('test_query_post_alarm_data_31'))                      # 31 VALIDATED
    suiteFew.addTest(TestSequenceFunctions('test_query_post_utility_data_32'))                    # 32 VALIDATED
    suiteFew.addTest(TestSequenceFunctions('test_tools_get_outage_region_50'))                    # 50 VALIDATED
    suiteFew.addTest(TestSequenceFunctions('test_utilities_get_eon_utility_entries_60'))          # 60 VALIDATED
    # suiteFew.addTest(TestSequenceFunctions('test_utilities_post_eon_utility_entry_61'))           # 61 NOT VALIDATED
    # test 61 (DOESNT AGREE w example on : Thu, Oct 2, 2014 at 9:57 AM)
    suiteFew.addTest(TestSequenceFunctions('test_utilities_get_eon_utility_by_id_62'))            # 62 VALIDATED
    suiteFew.addTest(TestSequenceFunctions('test_utilities_post_eon_utility_downstream_63'))      # 63 VALIDATED
    suiteFew.addTest(TestSequenceFunctions('test_utilities_post_eon_utility_associated_onts_64'))  # 64 VALIDATED
    suiteFew.addTest(TestSequenceFunctions('test_utilities_post_eon_utility_upstream_65'))        # 65 VALIDATED
    suiteFew.addTest(TestSequenceFunctions('test_utilities_get_eon_utility_circuit_by_id_66'))    # 66 VALIDATED
    suiteFew.addTest(TestSequenceFunctions('test_utilities_get_eon_utility_transformer_by_id_67'))  # 67 VALIDATED
    # suiteFew.addTest(TestSequenceFunctions('test_query_eon_area_a0'))                             # A0 VALIDATED
    # suiteFew.addTest(TestSequenceFunctions('test_query_waypoints_by_circuit_a1'))                 # A1 VALIDATED
    # suiteFew.addTest(TestSequenceFunctions('test_query_circuits_by_utility_a2'))                  # A2 VALIDATED
    unittest.TextTestRunner(verbosity=2).run(suiteFew)
    # unittest.TextTestRunner(verbosity=2).run(suite())
