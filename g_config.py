#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) 2014 Patrick Moran for Verizon
#
# Distributes WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# If not, see <http://www.gnu.org/licenses/>.

# This is the config file for the EON360 Outage algorithm

import socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.connect(("gmail.com", 80))
ip_address = s.getsockname()[0]
s.close()

if ip_address.find('192.168') < 0:
    IS_DEPLOYED = True
    print "Running on a deployed system"
else:
    IS_DEPLOYED = False
    print "Running on a localhost system through a tunnel"


if IS_DEPLOYED:
    BASE_DIR = '/local/home/pmoran/groomer'
else:
    BASE_DIR = 'C:\\repo\\Aptect\\Verizon\\Workproduct\\EON-IOT\\groomer'

LOG_DIR = 'logs'
PICKLES = 'pickles'

KEEP_ALIVE_INTERVAL = 20  # seconds
if IS_DEPLOYED:
    PROCESS_GROOM_TIME = 60*5  # seconds (5 minutes)
else:
    PROCESS_GROOM_TIME = 60  # seconds (1 minute)
# Consider the thread idle if IDLE_DETECT_TIME has expired
IDLE_DETECT_TIME = 4 * KEEP_ALIVE_INTERVAL

###########################
# Logger log file base name
EON_LOG_FILENAME_BASE = 'EON_LOG'


LOG_FORMAT = '%(asctime)s %(name)-12s %(levelname)-8s %(funcName)s %(lineno)5d :%(message)s'

# Change PRODUCTION to False if running on the development server
PRODUCTION = True

###########################
# INGESTOR API
# For testing locally I use putty and a tunnel for this port

if PRODUCTION:
    if IS_DEPLOYED:
        EON_INGESTOR_API_IP = '10.123.0.27'
    else:
        EON_INGESTOR_API_IP = 'localhost'
    EON_INGESTOR_API_PORT = 8080
else:
    if IS_DEPLOYED:
        EON_INGESTOR_API_IP = '10.122.116.17'
    else:
        EON_INGESTOR_API_IP = 'localhost'
    EON_INGESTOR_API_PORT = 28080

EON_INGESTOR_API_BASE = '/eon360/api'
EON_INGESTOR_UN = 'customer'
EON_INGESTOR_PW = 'customer'
# Individual API points
EON_INGESTOR_QUERY_API = 'query'
EON_INGESTOR_OUTAGES_API = 'outages'
EON_INGESTOR_ELIGIBILITIES_API = 'eligibilities'
EON_INGESTOR_ALARMS_API = 'alarms'
EON_INGESTOR_CIRCUITS_API = 'utilities/circuits'
# Example: Constructing the URL like this:
# EON_INGESTOR_URL='http://'+EON_INGESTOR_API_IP+':'+
#                  EON_INGESTOR_API_PORT+EON_INGESTOR_API_BASE+'/'+EON_INGESTOR_API_QUERY
# produces:
# EON_INGESTOR_URL="http://10.122.116.17:28080/eon360/api/query"
# PJM changed on 2/27/2015   EON_CUSTOMER_NAME='CETEST'
# EON_CUSTOMER_NAMES = ['CETEST']
EON_CUSTOMER_NAMES = ['CEDRAFT']

# There should be one dictionary entry for each EON_CUSTOMER_NAME
UTILITY_REGION = {'CEDRAFT': {'min_latitude': 40.451589,
                              'max_latitude': 41.403706,
                              'max_longitude': -73.592483,
                              'min_longitude': -74.308169}}

###########################
# MQ BUS CONNECTION


# For testing locally I use putty and a tunnel for this port
# EON_MQ_IP='10.122.116.12'
#  Manually the grooming  queue can be checked here:
# http://10.123.0.20:15672/#/queues/eon360/grooming-notification

if PRODUCTION:
    if IS_DEPLOYED:
        EON_MQ_IP = '10.123.0.20'
    else:
        EON_MQ_IP = 'localhost'
    EON_MQ_UN = 'eon360'
    EON_MQ_PW = 'e0n36o'
    EON_MQ_PORT = 5672
    EON_MQ_BASE = '/#/queues'
    EON_MQ_VHOST = 'eon360'
    EON_MQ_QUEUE = 'collection-notification'
    EON_GROOM_QUEUE = 'grooming-notification'
else:
    if IS_DEPLOYED:
        EON_MQ_IP = '10.122.116.12'
    else:
        EON_MQ_IP = 'localhost'
    EON_MQ_UN = 'eon360'
    EON_MQ_PW = 'eon360'
    EON_MQ_PORT = 5672
    EON_MQ_BASE = '/#/queues'
    EON_MQ_VHOST = 'eon360'
    EON_MQ_QUEUE = 'collection-notification'
    EON_GROOM_QUEUE = 'grooming-notification'

# Example: Constructing the URL like this:
# EON_MQ_URL='amqp://'+EON_MQ_UN+':'EON_MQ_PW+'@'+EON_MQ_IP+':'+
#                EON_MQ_PORT+EON_MQ_BASE+'/'+EON_MQ_VHOST+'/'+EON_MQ_QUEUE
# produces:
# EON_MQ_URL='amqp://eon360:eon360@192.168.0.28:5672/#/queues/eon360/collection-notification'

###############################
# Multiple Agent Control
# Size of the Queue that needs to be achieved before the outage alarms are processed
# This is used so that multiple agents can sit on the same bus. When one agent is busy then the
# next agent will have a chance to take over is the bus piles up.
QUEUE_SIZE_BLOCK = 3
# Number of seconds to wait before processing an incomplete queue depth
MESSAGE_EXPIRATION_SEC = 10.0
# Number of threads to run in this process.

if IS_DEPLOYED:
    # Use 75 for production
    NUM_THREADS = 10
else:
    NUM_THREADS = 1

# Number of circuits to process at a time in each thread chunk
# PJM changed on 2/27/2015 CIRCUIT_PROCESS_COUNT=20
CIRCUIT_PROCESS_COUNT = 20

MAX_OUTAGE_SIGNATURE = 10000
######################
# These are the new outage posting component code parameters
# The CONED CEDRAFT needs SQUARE_BOX_SIDE = 0.01
SQUARE_BOX_SIDE = 0.1  # number of degrees for the area search

# Time to sleep when trying to acquire a lock
SLEEP_TIME = 0.01

##############################
# Alarm detection algorithm
# RADIUS_UNITS can be ['KILOMETERS' or 'MILES' or 'NEUTRAL'],
RADIUS_UNITS = 'MILES'
# The CONED CEDRAFT needs START_RADIUS = 0.08
START_RADIUS = 0.12
ONT_POST_RADIUS = 1.0
# PJM changed on 2/27/2015   ONT_STOP_COUNT=10; # stopping number of ONT to look at in a region
ONT_STOP_COUNT = 3
#    VOTE_COUNT=5; # number of ONT to use for a majority vote.
# PJM changed on 2/27/2015 VOTE_COUNT=3
VOTE_COUNT = 3  # Number of ONTs to use for voting
VOTE_THRESHOLD = 0.5  # Threshold of the vote win
VOTE_BACK_STEP_COUNT = 1  # Number of alarms to look backward in time
#####################
# GROOMER DATA SETTINGS
# PJM changed on 2/27/2015 ALARM_DETECT_WINDOW seconds of detection window #  1 week = 604800
# All times are in msec
ALARM_DETECT_WINDOW = 60480  # Temporal window for vote in seconds (60480 is .7 days)
# This is the EPOCH time that is time.gmtime(1388538000)
# time.struct_time(tm_year=2014, tm_mon=1, tm_mday=1, tm_hour=1, tm_min=0, tm_sec=0, tm_wday=2, tm_yday=1, tm_isdst=0)
# about Jan 1, 2014
# This is in milliseconds
ENGINE_BEGIN_TIME = 1388538000000
MS_TIME_RESOLUTION = 5000  # 5 seconds
DEGLITCH_TIME = 5*60*1000

TTL_MAX = 3
# The TTL_UTILITY_SPAN will ensure that the entire utility is covered
# When the ttl is set to this value then the cells will propagate until the entire region is covered.
TTL_UTILITY_SPAN = -1
# The random TTL time is set to a level to so that the cell and surrounding cells are computed.
TTL_RANDOM_GROOM = 2
