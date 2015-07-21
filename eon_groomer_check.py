
import Queue
from g_pika_rabbit_bridge import MqConsumer, MqPublisher
import logging.handlers
import os
import threading
import datetime
import g_config
import time
import sys
import getopt
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

LOG_FILENAME = g_config.BASE_DIR  + os.sep + g_config.LOG_DIR + os.sep + 'top_' + unique_str + '.log'
# Add the log message handler to the logger
handler = logging.handlers.RotatingFileHandler(LOG_FILENAME, maxBytes=5000000, backupCount=50)
handler.setFormatter(logging.Formatter(g_config.LOG_FORMAT, datefmt='%m-%d %H:%M:%S'))
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
def groom_running_processes(my_logger, pool, shared_data, queue_lock):
    my_logger.info("GROOMING THREADS NOW: %f" % time.time())
    num_threads = len(pool)
    idle_test = [False] * num_threads
    for i, thisThread in enumerate(pool):
        # thisThread.idle_count is set in the eon_analyzer code and is incremented after each run loop call when the
        # analyzer is idle
        if (thisThread.idle_count * g_config.KEEP_ALIVE_INTERVAL) > g_config.IDLE_DETECT_TIME:
            my_logger.info("%s is idle after %d timeouts" % (thisThread.instance_name, thisThread.idle_count))
            idle_test[i] = True

    for i, thisThread in enumerate(pool):
        if idle_test[i] is False:
            my_logger.info("%s in state=%s, idle count=%d" %
                           (thisThread.instance_name, thisThread.analyzer_state, thisThread.idle_count)
                           )
    if all(idle_test):
        overall_alarm_count = 0
        overall_waypoint_count = 0
        elapsed = 0.0
        number_active_threads = 0
        for i, thisThread in enumerate(pool):
            if thisThread.alarm_count > 0:
                overall_alarm_count += thisThread.alarm_count
                overall_waypoint_count += thisThread.waypoint_count
                # max(elapsed, thisThread.end_time - thisThread.start_time)
                elapsed += thisThread.end_time - thisThread.start_time
                number_active_threads += 1
        if elapsed > 0.0:
            # Using the average of the elapsed time for the alarm rate.
            my_logger.info("Rate, %5.5f, (alarms/sec), "
                           "%5.5f, (waypoints/sec), # circuit_jobs=%d, # outage_signatures=%d" %
                           (float(overall_alarm_count*number_active_threads)/elapsed,
                            float(overall_waypoint_count*number_active_threads)/elapsed,
                            len(shared_data['circuits_jobs']),
                            len(shared_data['outage_signatures']))
                           )

            lock_counter = 0
            while not queue_lock.acquire(False):
                my_logger.debug("Trying to acquire lock. Sleeping  .05s.")
                time.sleep(g_config.SLEEP_TIME)
                lock_counter += 1
                if lock_counter > 100:
                    my_logger.error("Unable to acquire lock in eon_analytics")
            if len(shared_data['outage_signatures']) > g_config.MAX_OUTAGE_SIGNATURE:
                my_logger.debug("acquired lock resetting outage_signatures")
                shared_data['outage_signatures'] = set()
            queue_lock.release()
def main(argv):
    enable_console_log = False
    log_file_name = sys.stdout
    my_f_log_level = logging.DEBUG
    my_log_level = logging.INFO
    try:
        opts, args = getopt.getopt(argv, "hl:cL:f:", ["log=", "console", "level=", "file_level="])
    except getopt.GetoptError:
        print 'try g_main.py -h for more options'
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print 'g_main.py -l <console logfile>\nChange the destination of the console log output.\nUse -l with ' \
                  'no filename to enable console logging.\nExample:\n         python g_main.py -l console.log\n' \
                  'g_main.py -L <level>\nChange the log level to <level>\nLevel can be "debug", "info", "warning", ' \
                  '"critical" '
            sys.exit()
        elif opt in ("-c", "--console"):
            enable_console_log = True
        elif opt in ("-l", "--log"):
            log_file_name = arg
        elif opt in ("-L", "--level"):
            log_level = arg
            if log_level[0].lower() == 'd':
                my_log_level = logging.DEBUG
            elif log_level[0].lower() == 'i':
                my_log_level = logging.INFO
            elif log_level[0].lower() == 'w':
                my_log_level = logging.WARNING
            elif log_level[0].lower() == 'c':
                my_log_level = logging.CRITICAL
            else:
                print 'g_main.py -L %s is not recognized. \n Level can be d,i,w, or c' % log_level
                sys.exit(2)
        elif opt in ("-f", "--file_level"):
            f_log_level = arg
            if f_log_level[0].lower() == 'd':
                my_f_log_level = logging.DEBUG
            elif f_log_level[0].lower() == 'i':
                my_f_log_level = logging.INFO
            elif f_log_level[0].lower() == 'w':
                my_f_log_level = logging.WARNING
            elif f_log_level[0].lower() == 'c':
                my_f_log_level = logging.CRITICAL
            else:
                print 'g_main.py -f %s is not recognized. \n Level can be d,i,w, or c' % f_log_level
                sys.exit()

    if enable_console_log:
        console = logging.StreamHandler(log_file_name)
        console.setLevel(my_log_level)
        formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
        console.setFormatter(formatter)
        logging.getLogger('').addHandler(console)

    logging.getLogger('').setLevel(my_f_log_level)

    # set the logger name to be the name of this module
    my_logger = logging.getLogger(__name__)
    my_logger.setLevel(logging.INFO)
    # #######################
    # BEGIN CODE
    # ######################
    start_time = time.time()
    next_groom_time = start_time + g_config.PROCESS_GROOM_TIME

    connection_string = 'amqp://' + g_config.EON_MQ_UN + ':' + g_config.EON_MQ_PW + '@' + g_config.EON_MQ_IP + ':' + \
                        ('%d' % g_config.EON_MQ_PORT) + '/' + g_config.EON_MQ_VHOST
    my_logger.info("Connecting to '%s'" % connection_string)

    
            
            
# rabbit_message_queue = Queue.Queue()
# rabbit_queue_lock = threading.Lock()
# consumer = MqConsumer(connection_string, rabbit_message_queue, rabbit_queue_lock, EON_GROOM_QUEUE)
#
# # # Can probably use the next line to look for a failed pika bridge.
# # It will be None if the connection is not available.
# # consumer.__dict__['_connection']
# publish_message_queue = Queue.Queue()
# publish_queue_lock = threading.Lock()
# publisher = MqPublisher(connection_string, publish_message_queue, publish_queue_lock, EON_GROOM_QUEUE)
# groomer = GroomingMessageHandler(incoming_q=rabbit_message_queue,
#                                  incoming_queue_lock=rabbit_queue_lock,
#                                  outgoing_q=publish_message_queue,
#                                  outgoing_queue_lock=publish_queue_lock,
#                                  module_instance_name='Handler01',
#                                  shared_data=shared_data_top,
#                                  shared_data_lock=shared_data_lock_top)
# groomer.run_enable = True
# groomer.start()
# consumer.start()
# publisher.start()
# run_mode = True
#     groomer.join()
#     consumer.join()
#     publisher.join()
# except KeyboardInterrupt:
#     groomer.join()
#     # consumer.join()
