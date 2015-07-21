#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) 2014 Patrick Moran for Verizon
#
# Distributes WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License. If not, see <http://www.gnu.org/licenses/>.

import logging
import logging.handlers
import time
import g_config
import Queue
import os
import threading
from eon_groomer import GroomingMessageHandler
from g_pika_rabbit_bridge import MqConsumer, MqPublisher
import sys
import getopt
import datetime

########################
# LOG FILE SETUP
########################
unique_str = datetime.datetime.now().isoformat().replace(':', '_').replace('.', '_').replace('-', '_')
if g_config.IS_DEPLOYED:
    try:
        os.mkdir(g_config.BASE_DIR + os.sep + g_config.LOG_DIR)
    except OSError as e:
        print "Warning : %s" % e
else:
    try:
        os.mkdir(g_config.BASE_DIR + os.sep + g_config.LOG_DIR)                
    except WindowsError as e:
        print "Warning : %s" % e
                
if g_config.IS_DEPLOYED:
    try:
        os.mkdir(g_config.BASE_DIR + os.sep + g_config.PICKLES)
    except OSError as e:
        print "Warning : %s" % e     
else:
    try:
        os.mkdir(g_config.BASE_DIR + os.sep + g_config.PICKLES)                
    except WindowsError as e:
        print "Warning : %s" % e

LOG_FILENAME = g_config.BASE_DIR + os.sep + g_config.LOG_DIR + os.sep + 'top_'+unique_str+'.log'
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


def groom_running_processes(my_logger, pool):
    my_logger.info("GROOMING THREADS NOW: %f" % time.time())
    num_threads = len(pool)
    idle_test = [False] * num_threads
    for i, thisThread in enumerate(pool):
        if not g_config.IS_DEPLOYED:
            print "  Check IDLE on thread %s." % thisThread.instance_name
        # thisThread.idle_count is set in the eon_groomer code and is incremented after each run loop call when the
        # analyzer is idle
        if (thisThread.idle_count * g_config.KEEP_ALIVE_INTERVAL) > g_config.IDLE_DETECT_TIME:
            if not g_config.IS_DEPLOYED:
                print "    %s is idle after %d time outs" % (thisThread.instance_name, thisThread.idle_count)
            my_logger.info("%s is idle after %d time outs" % (thisThread.instance_name, thisThread.idle_count))
            idle_test[i] = True
        else:  # if idle_test[i] is False:
            if not g_config.IS_DEPLOYED:
                print "    %s is not idle yet! It's in state=%s, groomer state=%s,  idle count=%d" % \
                      (thisThread.instance_name, thisThread.groom_run_state,
                       thisThread.groomer_state, thisThread.idle_count)
            my_logger.info("%s is not idle yet! It's in state=%s, groomer state=%s, idle count=%d" %
                           (thisThread.instance_name, thisThread.groom_run_state,
                            thisThread.groomer_state, thisThread.idle_count)
                           )
    if all(idle_test):
        if not g_config.IS_DEPLOYED:
            print "  All threads are idle. Firing up a Utility wide groom process"
        # Just fire up one thread because the others will pick it up:
        pool[0].utility_groom()


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

    rabbit_message_queue = Queue.Queue()
    # The lock is used to ensure that multiple threads pulling off the internal queue don't stomp on each other.
    # The threads each have to grab a thread lock before taking items off teh queue then release it immediately.
    rabbit_queue_lock = threading.Lock()
    # Instantiate a Consumer thread. This thread pulls items off the bus as they arrive and puts
    # them on the rabbit_message_queue
    # example = MQ_Dispatcher('amqp://guest:guest@localhost:5672/%2F')
    consumer = MqConsumer(connection_string, rabbit_message_queue, rabbit_queue_lock, g_config.EON_GROOM_QUEUE)
    # Can probably use the next line to look for a failed pika bridge. It will be None is the
    # connection is not available.
    # consumer.__dict__['_connection']
    publish_message_queue = Queue.Queue()
    publish_queue_lock = threading.Lock()
    publisher = MqPublisher(connection_string, publish_message_queue, publish_queue_lock, g_config.EON_GROOM_QUEUE)
    # Instantiate a Backend Message Handler thread. There can be many backend threads set by config.NUM_THREADS.
    pool = []
    for i in range(g_config.NUM_THREADS):
        pool.append(GroomingMessageHandler(incoming_q=rabbit_message_queue,
                                           incoming_queue_lock=rabbit_queue_lock,
                                           outgoing_q=publish_message_queue,
                                           outgoing_queue_lock=publish_queue_lock,
                                           module_instance_name=('Handler%d' % i),
                                           shared_data=shared_data_top,
                                           shared_data_lock=shared_data_lock_top))
                                           
    # Start things up.
    for i in range(g_config.NUM_THREADS):
        pool[i].run_enable = True
        pool[i].start()

    consumer.start()
    publisher.start()
    # Prepare the main event loop.
    run_mode = True
    if not g_config.IS_DEPLOYED:
        print '%d threads up and running at time=%f' % (g_config.NUM_THREADS, time.time())
    my_logger.info('%d threads up and running at time=%f' % (g_config.NUM_THREADS, time.time()))
    try:
        # here's where we can do other stuff (like the test routines)
        while run_mode:
            if time.time() > next_groom_time:
                if not g_config.IS_DEPLOYED:
                    print "Reached groom time!"
                my_logger.info("Reached groom time!")
                groom_running_processes(my_logger, pool)
                next_groom_time = time.time() + g_config.PROCESS_GROOM_TIME

    # TODO:
    # Add an exception for a failure in the main program.
    except KeyboardInterrupt:
        my_logger.info("Keyboard interrupt!")
        for i in range(g_config.NUM_THREADS):
            pool[i].run_enable = False
            pool[i].join()
        my_logger.info("Thread pool joined")
        publisher.stop()
        publisher.join()
        consumer.stop()
        consumer.join()

if __name__ == '__main__':
    myLogger = logging.getLogger(__name__)
    myLogger.info("Starting main loop")
    os.chdir(g_config.BASE_DIR)
    main(sys.argv[1:])
    myLogger.info("MAIN HAS ENDED")
