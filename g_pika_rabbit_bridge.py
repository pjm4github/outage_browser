#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) 2014 Patrick Moran for Verizon
#
# Distributes WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License.  If not, see <http://www.gnu.org/licenses/>.

import logging
import json
import pika
import g_config
import threading
import time
import copy
# import inspect
# LOG_FORMAT = ('%(levelname) -10s %(asctime)s %(name) -30s %(funcName) '
#              '-35s %(lineno) -5d: %(message)s')
# LOGGER = logging.getLogger(__name__)


class MqConsumer(threading.Thread):
    """
    This is a consumer that handles interactions with RabbitMQ. Messages that appear on the Outage Alarm Queue will be
    consumed by this object. This object maintains a persistent socket connection.

    If RabbitMQ closes the connection, it will reopen it.
    There are limited reasons why the connection may be closed,
    which usually are tied to permission related issues or
    socket timeouts.

    If the channel is closed, it will indicate a problem with one of the
    commands that were issued and that should surface in the output as well.
    """
    def __init__(self, amqp_url, consumer_queue=None, consumer_queue_lock=None, ampq_queue=None):
        """Create a new instance of the consumer class, passing in the AMQP
        URL used to connect to RabbitMQ.
        :param str amqp_url: The AMQP url to connect with
        """
        self._connection = None
        self._channel = None
        self._closing = False
        self._consumer_tag = None
        self._url = amqp_url
        self.EXCHANGE = ''
        self.EXCHANGE_TYPE = 'topic'
        self.ROUTING_KEY = ''
        if ampq_queue:
            self.AMPQ_QUEUE = ampq_queue
        else:
            self.AMPQ_QUEUE = g_config.EON_MQ_QUEUE
        self.consumer_queue = consumer_queue
        self.consumer_queue_lock = consumer_queue_lock
        self.my_local_logger = logging.getLogger(__name__)
        self.my_local_logger.setLevel(logging.ERROR)
        threading.Thread.__init__(self)

    def connect(self):
        """This method connects to RabbitMQ, returning the connection handle.
        When the connection is established, the on_connection_open method
        will be invoked by pika.

        :rtype: pika.SelectConnection

        """
        self.my_local_logger.info('Connecting to %s', self._url)
        try:
            return pika.SelectConnection(pika.URLParameters(self._url),
                                         self.on_connection_open,
                                         stop_ioloop_on_close=False)
        except pika.exceptions.AMQPConnectionError as e:
            self.my_local_logger.error('NO CONNECTION to %s because %s', (self._url, e))
            exit()

    def close_connection(self):
        """This method closes the connection to RabbitMQ."""
        self.my_local_logger.debug('Closing connection')
        self._connection.close()

    def add_on_connection_close_callback(self):
        """This method adds an on close callback that will be invoked by pika
        when RabbitMQ closes the connection to the publisher unexpectedly.

        """
        self.my_local_logger.debug('Adding connection close callback')
        self._connection.add_on_close_callback(self.on_connection_closed)

    def on_connection_closed(self, connection, reply_code, reply_text):
        """This method is invoked by pika when the connection to RabbitMQ is
        closed unexpectedly. Since it is unexpected, we will reconnect to
        RabbitMQ if it disconnects.

        :param pika.connection.Connection connection: The closed connection obj
        :param int reply_code: The server provided reply_code if given
        :param str reply_text: The server provided reply_text if given

        """
        self._channel = None
        if self._closing:
            self._connection.ioloop.stop()
        else:
            self.my_local_logger.warning('Connection closed, reopening in 5 seconds: (%s) %s',
                                         reply_code, reply_text)
            self._connection.add_timeout(5, self.reconnect)

    def on_connection_open(self, unused_connection):
        """This method is called by pika once the connection to RabbitMQ has
        been established. It passes the handle to the connection object in
        case we need it, but in this case, we'll just mark it unused.

        :type unused_connection: pika.SelectConnection

        """
        self.my_local_logger.debug('Connection opened')
        self.add_on_connection_close_callback()
        self.open_channel()

    def reconnect(self):
        """Will be invoked by the IOLoop timer if the connection is
        closed. See the on_connection_closed method.

        """
        # This is the old connection IOLoop instance, stop its ioloop
        self._connection.ioloop.stop()

        if not self._closing:
            # Create a new connection
            self._connection = self.connect()

            # There is now a new connection, needs a new ioloop to run
            self._connection.ioloop.start()

    def add_on_channel_close_callback(self):
        """This method tells pika to call the on_channel_closed method if
        RabbitMQ unexpectedly closes the channel.

        """
        self.my_local_logger.debug('Adding channel close callback')
        self._channel.add_on_close_callback(self.on_channel_closed)

    def on_channel_closed(self, channel, reply_code, reply_text):
        """Invoked by pika when RabbitMQ unexpectedly closes the channel.
        Channels are usually closed if you attempt to do something that
        violates the protocol, such as re-declare an exchange or queue with
        different parameters. In this case, we'll close the connection
        to shutdown the object.

        :param pika.channel.Channel: The closed channel
        :param int reply_code: The numeric reason the channel was closed
        :param str reply_text: The text reason the channel was closed

        """
        self.my_local_logger.warning('Channel %i was closed: (%s) %s',
                                     channel, reply_code, reply_text)
        self._connection.close()

    def on_channel_open(self, channel):
        """This method is invoked by pika when the channel has been opened.
        The channel object is passed in so we can make use of it.

        Since the channel is now open, we'll declare the exchange to use.

        :param pika.channel.Channel channel: The channel object

        """
        self.my_local_logger.debug('Channel opened')
        self._channel = channel
        self.add_on_channel_close_callback()
        self.setup_exchange(self.EXCHANGE)

    def setup_exchange(self, exchange_name):
        """Setup the exchange on RabbitMQ by invoking the Exchange.Declare RPC
        command. When it is complete, the on_exchange_declareok method will
        be invoked by pika.

        :param str|unicode exchange_name: The name of the exchange to declare

        """
        self.my_local_logger.debug('Declaring exchange %s', exchange_name)
        # self._channel.exchange_declare(self.on_exchange_declareok,
        #                               exchange_name,
        #                               self.EXCHANGE_TYPE)
        self.on_exchange_declareok(0)

    def on_exchange_declareok(self, unused_frame):
        """Invoked by pika when RabbitMQ has finished the Exchange.Declare RPC
        command.

        :param pika.Frame.Method unused_frame: Exchange.DeclareOk response frame

        """
        self.my_local_logger.debug('Exchange declared')
        self.setup_queue(self.AMPQ_QUEUE)

    def setup_queue(self, queue_name):
        """Setup the queue on RabbitMQ by invoking the Queue.Declare RPC
        command. When it is complete, the on_queue_declareok method will
        be invoked by pika.

        :param str|unicode queue_name: The name of the queue to declare.

        """
        self.my_local_logger.debug('Declaring queue %s', queue_name)
        # self._channel.queue_declare(self.on_queue_declareok, queue_name)
        self.on_queue_declareok(0)

    def on_queue_declareok(self, method_frame):
        """Method invoked by pika when the Queue.Declare RPC call made in
        setup_queue has completed. In this method we will bind the queue
        and exchange together with the routing key by issuing the Queue.Bind
        RPC command. When this command is complete, the on_bindok method will
        be invoked by pika.

        :param pika.frame.Method method_frame: The Queue.DeclareOk frame

        """
        self.my_local_logger.debug('Binding %s to %s with %s',
                                  self.EXCHANGE, self.AMPQ_QUEUE, self.ROUTING_KEY)
        # self._channel.queue_bind(self.on_bindok, self.AMPQ_QUEUE,
        #                         self.EXCHANGE, self.ROUTING_KEY)
        self.on_bindok(0)

    def add_on_cancel_callback(self):
        """Add a callback that will be invoked if RabbitMQ cancels the consumer
        for some reason. If RabbitMQ does cancel the consumer,
        on_consumer_cancelled will be invoked by pika.

        """
        self.my_local_logger.debug('Adding consumer cancellation callback')
        self._channel.add_on_cancel_callback(self.on_consumer_cancelled)

    def on_consumer_cancelled(self, method_frame):
        """Invoked by pika when RabbitMQ sends a Basic.Cancel for a consumer
        receiving messages.

        :param pika.frame.Method method_frame: The Basic.Cancel frame

        """
        self.my_local_logger.debug('Consumer was cancelled remotely, shutting down: %r',
                    method_frame)
        if self._channel:
            self._channel.close()

    def acknowledge_message(self, delivery_tag):
        """Acknowledge the message delivery from RabbitMQ by sending a
        Basic.Ack RPC method for the delivery tag.

        :param int delivery_tag: The delivery tag from the Basic.Deliver frame

        """
        self.my_local_logger.debug('Acknowledging message %s', delivery_tag)
        self._channel.basic_ack(delivery_tag)

    def on_message(self, unused_channel, basic_deliver, properties, body):
        """Invoked by pika when a message is delivered from RabbitMQ. The
        channel is passed for your convenience. The basic_deliver object that
        is passed in carries the exchange, routing key, delivery tag and
        a redelivered flag for the message. The properties passed in is an
        instance of BasicProperties with the message properties and the body
        is the message that was sent.

        :param pika.channel.Channel unused_channel: The channel object
        :param pika.Spec.Basic.Deliver: basic_deliver method
        :param pika.Spec.BasicProperties: properties
        :param str|unicode body: The message body
        """
        payload = json.loads(body)
        # This is what a grooming payload should look like:
        # {
        #   "queryGuid": "4a1b34bc-9739-4b40-85e1-8f464fe98211",
        #   "dateTime": "2015-05-03T19:42:33.689-0400",
        #   "payload": {
        #     "zoomR": 1,
        #     "spatial": "[1,0; .2,.2; .3,.01]",
        #     "circuitID": "59U3",
        #     "reputationEnabled": true,
        #     "assetID": "HS870f64df4bfe57ba2667f9add9e2588f",
        #     "temporal": "[1,0; .8,24; .3, 60]",
        #     "outageTime": 1430452800000,
        #     "company": "CEDRAFT",
        #     "votes": 3,
        #     "zoomT": 1,
        #     "longitude": -74.011081,
        #     "latitude": 41.07597
        #   },
        #   "messageType": "Query"
        if payload:
            while not self.consumer_queue_lock.acquire(False):
                self.my_local_logger.debug('Pika bridge waiting to acquire lock.')
                time.sleep(g_config.SLEEP_TIME)
            self.my_local_logger.debug('Pika bridge acquired lock.')
            try:

                self.consumer_queue.put(payload, False)
            except ValueError as e:
                self.my_local_logger.error("Exception occurred when extracting data from payload. "
                                           "Message is dropped. %s" % e )
                self.consumer_queue_lock.release()
            except NameError as e:
                self.my_local_logger.error("Exception occurred when extracting data from payload. %s" % e )
                self.consumer_queue_lock.release()
            except self.consumer_queue.Full:
                self.my_local_logger.error("Exception occurred when calling self.consumer_queue.put(): queue full")
                self.consumer_queue_lock.release()
            self.consumer_queue_lock.release()
            self.my_local_logger.debug('Lock released by pika')
            self.my_local_logger.debug('Received message # %s from %s: %s', basic_deliver.delivery_tag, properties.app_id, body)
            self.acknowledge_message(basic_deliver.delivery_tag)
        else:
            self.my_local_logger.info("payload is not a json structure, dumping the message")
            print "payload is not a json structure, dumping the message"
            self.acknowledge_message(basic_deliver.delivery_tag)

    def on_cancelok(self, unused_frame):
        """This method is invoked by pika when RabbitMQ acknowledges the
        cancellation of a consumer. At this point we will close the channel.
        This will invoke the on_channel_closed method once the channel has been
        closed, which will in-turn close the connection.

        :param pika.frame.Method unused_frame: The Basic.CancelOk frame

        """
        self.my_local_logger.info('RabbitMQ acknowledged the cancellation of the consumer')
        self.close_channel()

    def stop_consuming(self):
        """Tell RabbitMQ that you would like to stop consuming by sending the
        Basic.Cancel RPC command.

        """
        if self._channel:
            self.my_local_logger.info('Sending a Basic.Cancel RPC command to RabbitMQ')
            self._channel.basic_cancel(self.on_cancelok, self._consumer_tag)

    def start_consuming(self):
        """This method sets up the consumer by first calling
        add_on_cancel_callback so that the object is notified if RabbitMQ
        cancels the consumer. It then issues the Basic.Consume RPC command
        which returns the consumer tag that is used to uniquely identify the
        consumer with RabbitMQ. We keep the value to use it when we want to
        cancel consuming. The on_message method is passed in as a callback pika
        will invoke when a message is fully received.

        """
        self.my_local_logger.info('Issuing consumer related RPC commands')
        self.add_on_cancel_callback()
        self._consumer_tag = self._channel.basic_consume(self.on_message,
                                                         self.AMPQ_QUEUE)

    def on_bindok(self, unused_frame):
        """Invoked by pika when the Queue.Bind method has completed. At this
        point we will start consuming messages by calling start_consuming
        which will invoke the needed RPC commands to start the process.

        :param pika.frame.Method unused_frame: The Queue.BindOk response frame

        """
        self.my_local_logger.info('Queue bound')
        self.start_consuming()

    def close_channel(self):
        """Call to close the channel with RabbitMQ cleanly by issuing the
        Channel.Close RPC command.

        """
        self.my_local_logger.info('Closing the channel')
        self._channel.close()

    def open_channel(self):
        """Open a new channel with RabbitMQ by issuing the Channel.Open RPC
        command. When RabbitMQ responds that the channel is open, the
        on_channel_open callback will be invoked by pika.

        """
        self.my_local_logger.info('Creating a new channel')
        self._connection.channel(on_open_callback=self.on_channel_open)

    def run(self):
        """Run the consumer by connecting to RabbitMQ and then
        starting the IOLoop to block and allow the SelectConnection to operate.

        """
        # Instead of this connection we could use the QT event loop. See
        # https://gist.github.com/rickardp/2da1bf478de759cb2e15
        # This app will be headless so I wont use a GUI for now.
        while True:
            self._connection = self.connect()
            try:
                self._connection.ioloop.start()
            except:
                self.my_local_logger.info("WATCHDOG: PIKA BRIDGE DIDN'T START")
                # This will kill the process. The cron job should catch this and restart the service.
                # FIXME: This should be uncommented to enable the exit() call.
                exit()

    def stop(self):
        """Cleanly shutdown the connection to RabbitMQ by stopping the consumer
        with RabbitMQ. When RabbitMQ confirms the cancellation, on_cancelok
        will be invoked by pika, which will then closing the channel and
        connection. The IOLoop is started again because this method is invoked
        when CTRL-C is pressed raising a KeyboardInterrupt exception. This
        exception stops the IOLoop which needs to be running for pika to
        communicate with RabbitMQ. All of the commands issued prior to starting
        the IOLoop will be buffered but not processed.

        """
        self.my_local_logger.info('Stopping')
        self._closing = True
        self.stop_consuming()
        self._connection.ioloop.stop()
        self.my_local_logger.info('Stopped')


class MqPublisher(threading.Thread):
    """This is a publisher that will handle unexpected interactions
    with RabbitMQ such as channel and connection closures.

    If RabbitMQ closes the connection, it will reopen it. You should
    look at the output, as there are limited reasons why the connection may
    be closed, which usually are tied to permission related issues or
    socket timeouts.

    It uses delivery confirmations and illustrates one way to keep track of
    messages that have been sent and if they've been confirmed by RabbitMQ.

    see
    https://pika.readthedocs.org/en/0.9.14/examples/asynchronous_publisher_example.html
    """

    def __init__(self, amqp_url, publisher_queue, publisher_queue_lock, ampq_queue=None):
        """Setup the example publisher object, passing in the URL we will use
        to connect to RabbitMQ.

        :param str amqp_url: The URL for connecting to RabbitMQ
        :param str ampq_queue: The queue name to attach to on the RabbitMQ bus

        """
        self._deliveries = []
        self._acked = 0
        self._nacked = 0
        self._message_number = 0
        self._stopping = False
        self._connection = None
        self._channel = None
        self._closing = False
        self._consumer_tag = None
        self._url = amqp_url
        self.PUBLISH_INTERVAL = .2
        self.EXCHANGE = ''
        self.EXCHANGE_TYPE = 'topic'
        self.ROUTING_KEY = 'grooming-notification'
        if ampq_queue:
            self.AMPQ_QUEUE = ampq_queue
        else:
            self.AMPQ_QUEUE = g_config.EON_MQ_QUEUE
        self.my_local_logger = logging.getLogger(__name__)
        self.my_local_logger.setLevel(logging.INFO)
        self.message = None
        # This is the message queue that will be filled by another Python thread and will be flushed by the publisher
        self.publisher_queue = publisher_queue
        self.publisher_queue_lock = publisher_queue_lock
        # see http://pymotw.com/2/threading/
        self.event = threading.Event()
        self.publish_idle_count = 0
        threading.Thread.__init__(self)

    def connect(self):
        """This method connects to RabbitMQ, returning the connection handle.
        When the connection is established, the on_connection_open method
        will be invoked by pika. If you want the reconnection to work, make
        sure you set stop_ioloop_on_close to False, which is not the default
        behavior of this adapter.

        :rtype: pika.SelectConnection

        """
        self.my_local_logger.info('Connecting to %s', self._url)
        return pika.SelectConnection(pika.URLParameters(self._url),
                                     self.on_connection_open,
                                     stop_ioloop_on_close=False)

    def close_connection(self):
        """This method closes the connection to RabbitMQ."""
        self.my_local_logger.info('Closing connection')
        self._closing = True
        self._connection.close()

    def add_on_connection_close_callback(self):
        """This method adds an on close callback that will be invoked by pika
        when RabbitMQ closes the connection to the publisher unexpectedly.

        """
        self.my_local_logger.info('Adding connection close callback')
        self._connection.add_on_close_callback(self.on_connection_closed)

    def on_connection_closed(self, connection, reply_code, reply_text):
        """This method is invoked by pika when the connection to RabbitMQ is
        closed unexpectedly. Since it is unexpected, we will reconnect to
        RabbitMQ if it disconnects.

        :param pika.connection.Connection connection: The closed connection obj
        :param int reply_code: The server provided reply_code if given
        :param str reply_text: The server provided reply_text if given

        """
        self._channel = None
        if self._closing:
            self._connection.ioloop.stop()
        else:
            self.my_local_logger.warning('Connection closed, reopening in 5 seconds: (%s) %s',
                                         reply_code, reply_text)
            self._connection.add_timeout(5, self.reconnect)

    def on_connection_open(self, unused_connection):
        """This method is called by pika once the connection to RabbitMQ has
        been established. It passes the handle to the connection object in
        case we need it, but in this case, we'll just mark it unused.

        :type unused_connection: pika.SelectConnection

        """
        self.my_local_logger.info('Connection opened')
        self.add_on_connection_close_callback()
        self.open_channel()

    def reconnect(self):
        """Will be invoked by the IOLoop timer if the connection is
        closed. See the on_connection_closed method.

        """
        # This is the old connection IOLoop instance, stop its ioloop
        self._connection.ioloop.stop()

        # Create a new connection
        self._connection = self.connect()

        # There is now a new connection, needs a new ioloop to run
        self._connection.ioloop.start()

    def add_on_channel_close_callback(self):
        """This method tells pika to call the on_channel_closed method if
        RabbitMQ unexpectedly closes the channel.

        """
        self.my_local_logger.info('Adding channel close callback')
        self._channel.add_on_close_callback(self.on_channel_closed)

    def on_channel_closed(self, channel, reply_code, reply_text):
        """Invoked by pika when RabbitMQ unexpectedly closes the channel.
        Channels are usually closed if you attempt to do something that
        violates the protocol, such as re-declare an exchange or queue with
        different parameters. In this case, we'll close the connection
        to shutdown the object.

        :param pika.channel.Channel: The closed channel
        :param int reply_code: The numeric reason the channel was closed
        :param str reply_text: The text reason the channel was closed

        """
        self.my_local_logger.warning('Channel was closed: (%s) %s', reply_code, reply_text)
        if not self._closing:
            self._connection.close()

    def on_channel_open(self, channel):
        """This method is invoked by pika when the channel has been opened.
        The channel object is passed in so we can make use of it.

        Since the channel is now open, we'll declare the exchange to use.

        :param pika.channel.Channel channel: The channel object

        """
        self.my_local_logger.info('Channel opened')
        self._channel = channel
        self.add_on_channel_close_callback()
        self.setup_exchange(self.EXCHANGE)

    def setup_exchange(self, exchange_name):
        """Setup the exchange on RabbitMQ by invoking the Exchange.Declare RPC
        command. When it is complete, the on_exchange_declareok method will
        be invoked by pika.

        :param str|unicode exchange_name: The name of the exchange to declare

        """
        self.my_local_logger.info('Declaring exchange %s', exchange_name)
        # Removed this because the exchange name cant be a null string
        # self._channel.exchange_declare(self.on_exchange_declareok,
        #                               exchange_name,
        #                               self.EXCHANGE_TYPE)
        self.on_exchange_declareok(0)

    def on_exchange_declareok(self, unused_frame):
        """Invoked by pika when RabbitMQ has finished the Exchange.Declare RPC
        command.

        :param pika.Frame.Method unused_frame: Exchange.DeclareOk response frame

        """
        self.my_local_logger.info('Exchange declared')
        self.setup_queue(self.AMPQ_QUEUE)

    def setup_queue(self, queue_name):
        """Setup the queue on RabbitMQ by invoking the Queue.Declare RPC
        command. When it is complete, the on_queue_declareok method will
        be invoked by pika.

        :param str|unicode queue_name: The name of the queue to declare.

        """
        self.my_local_logger.info('Declaring queue %s', queue_name)
        # self._channel.queue_declare(self.on_queue_declareok, queue_name)
        self.on_queue_declareok(0)

    def on_queue_declareok(self, method_frame):
        """Method invoked by pika when the Queue.Declare RPC call made in
        setup_queue has completed. In this method we will bind the queue
        and exchange together with the routing key by issuing the Queue.Bind
        RPC command. When this command is complete, the on_bindok method will
        be invoked by pika.

        :param pika.frame.Method method_frame: The Queue.DeclareOk frame

        """
        self.my_local_logger.info('Binding %s to %s with %s',
                                  self.EXCHANGE, self.AMPQ_QUEUE, self.ROUTING_KEY)

        # self._channel.queue_bind(self.on_bindok, self.AMPQ_QUEUE,
        #                          self.EXCHANGE, self.ROUTING_KEY)

        # self._channel.queue_bind(self.on_bindok, self.AMPQ_QUEUE, '', '')
        self.on_bindok(0)

    def on_delivery_confirmation(self, method_frame):
        """Invoked by pika when RabbitMQ responds to a Basic.Publish RPC
        command, passing in either a Basic.Ack or Basic.Nack frame with
        the delivery tag of the message that was published. The delivery tag
        is an integer counter indicating the message number that was sent
        on the channel via Basic.Publish. Here we're just doing house keeping
        to keep track of stats and remove message numbers that we expect
        a delivery confirmation of from the list used to keep track of messages
        that are pending confirmation.

        :param pika.frame.Method method_frame: Basic.Ack or Basic.Nack frame

        """
        confirmation_type = method_frame.method.NAME.split('.')[1].lower()
        self.my_local_logger.debug('Received %s for delivery tag: %i',
                                   confirmation_type,
                                   method_frame.method.delivery_tag)
        if confirmation_type == 'ack':
            self._acked += 1
        elif confirmation_type == 'nack':
            self._nacked += 1
        self._deliveries.remove(method_frame.method.delivery_tag)
        self.my_local_logger.debug('Published %i messages, %i have yet to be confirmed, '
                                   '%i were acked and %i were nacked',
                                   self._message_number, len(self._deliveries),
                                   self._acked, self._nacked)

    def enable_delivery_confirmations(self):
        """Send the Confirm.Select RPC method to RabbitMQ to enable delivery
        confirmations on the channel. The only way to turn this off is to close
        the channel and create a new one.

        When the message is confirmed from RabbitMQ, the
        on_delivery_confirmation method will be invoked passing in a Basic.Ack
        or Basic.Nack method from RabbitMQ that will indicate which messages it
        is confirming or rejecting.

        """
        self.my_local_logger.info('Issuing Confirm.Select RPC command')
        self._channel.confirm_delivery(self.on_delivery_confirmation)

    def publish_message(self):
        """If the class is not stopping, publish a message to RabbitMQ,
        appending a list of deliveries with the message number that was sent.
        This list will be used to check for delivery confirmations in the
        on_delivery_confirmations method.

        Once the message has been sent, schedule another message to be sent.
        The main reason I put scheduling in was just so you can get a good idea
        of how the process is flowing by slowing down and speeding up the
        delivery intervals by changing the PUBLISH_INTERVAL constant in the
        class.

        """
        if self._stopping:
            return

        if not self._channel:
            print "Publish channel has not been established yet"
            return
        lock_counter = 0
        # Acquire the lock here
        while not self.publisher_queue_lock.acquire(False):
            self.my_local_logger.debug("MqDispatcher:Trying to acquire lock. Sleeping  0.05s.")
            time.sleep(g_config.SLEEP_TIME)
            lock_counter += 1
            if lock_counter > 100:
                self.my_local_logger.error("MqDispatcher:Unable to acquire lock in 100 tries, "
                                           "returning without publishing ")
                self.schedule_next_message()
                return
        #if self.publisher_queue_lock:
        #    print "Publisher acquired lock, lock_counter=%d" % lock_counter
        #else:
        #    print "Publisher didn't acquire lock, lock_counter=%d" % lock_counter
        self.publish_idle_count += 1
        while (self.message is not None) or (not self.publisher_queue.empty()):
            if not self.publisher_queue.empty():
                self.message = copy.copy(self.publisher_queue.get())
                # print 'Publisher got 1 message. Queue size is now %d' % self.publisher_queue.qsize()
                self.my_local_logger.info('Bridge got 1 message. Queue size is %d' % self.publisher_queue.qsize())
            else:
                # don't really pull the message if the queue is empty.
                # print 'Publisher no message available now'
                self.my_local_logger.debug("Publisher no message available now.")

            print "Publisher sending: %s" % self.message
            # content_type='application/json',,
            # content_encoding='utf-8',
            # headers=header_data,   header_data = {'key': 'value'}
            # delivery_mode=None,
            # priority=None,
            # correlation_id=None,
            # reply_to=None,
            # expiration=None,
            # message_id=None,
            # timestamp=None,
            # type=None,
            # user_id=None,
            # app_id='MqPublisher',
            # cluster_id=None

            properties = pika.BasicProperties(app_id='groomer-broadcast',
                                              content_type='application/json',
                                              content_encoding='utf-8',
                                              delivery_mode=2  # Persistent
                                              ) # headers={})

            self._channel.basic_publish(exchange=self.EXCHANGE, routing_key=self.ROUTING_KEY,
                                        body=json.dumps(self.message, ensure_ascii=False),
                                        properties=properties)
            # self._channel.basic_publish(body=json.dumps(message, ensure_ascii=False))
            self._message_number += 1
            self._deliveries.append(self._message_number)
            print 'Published message # %d' % self._message_number
            self.my_local_logger.info('Published message # %d', self._message_number)
            self.message = None
            self.publish_idle_count = 0
        self.my_local_logger.debug('No message now. Last message # %d', self._message_number)
        if self.publisher_queue_lock:
            self.publisher_queue_lock.release()
            self.my_local_logger.debug('Publisher lock released.')
            # print 'Publisher lock released'
        self.schedule_next_message()

    def schedule_next_message(self):
        """If we are not closing our connection to RabbitMQ, schedule another
        message to be delivered in PUBLISH_INTERVAL seconds.

        """
        if self._stopping:
            return
        self.my_local_logger.debug('Scheduling next message for %0.1f seconds',
                                  self.PUBLISH_INTERVAL)

        self._connection.add_timeout(self.PUBLISH_INTERVAL,
                                     self.publish_message)

    def start_publishing(self):
        """This method will enable delivery confirmations and schedule the
        first message to be sent to RabbitMQ

        """
        self.my_local_logger.info('Issuing consumer related RPC commands')
        self.enable_delivery_confirmations()
        self.schedule_next_message()

    def on_bindok(self, unused_frame):
        """This method is invoked by pika when it receives the Queue.BindOk
        response from RabbitMQ. Since we know we're now setup and bound, it's
        time to start publishing."""
        self.my_local_logger.info('Queue bound')
        self.start_publishing()

    def close_channel(self):
        """Invoke this command to close the channel with RabbitMQ by sending
        the Channel.Close RPC command.

        """
        self.my_local_logger.info('Closing the channel')
        if self._channel:
            self._channel.close()

    def open_channel(self):
        """This method will open a new channel with RabbitMQ by issuing the
        Channel.Open RPC command. When RabbitMQ confirms the channel is open
        by sending the Channel.OpenOK RPC reply, the on_channel_open method
        will be invoked.

        """
        self.my_local_logger.info('Creating a new channel')
        self._connection.channel(on_open_callback=self.on_channel_open)

    def run(self):
        """Run the example code by connecting and then starting the IOLoop.

        """
        # self._connection = self.connect()
        # self._connection.ioloop.start()
        running = True
        while running:
            self._connection = self.connect()
            # see http://pymotw.com/2/threading/
            #  self._connection._on_data_available()
            try:
                self._connection.ioloop.start()

            except:
                self.my_local_logger.warning('WATCHDOG: PIKA PUBLISHER DID NOT START')
                # This will kill the process. The cron job should catch this and restart the service.
                # exit()
            if self._stopping:
                running = False

    def stop(self):
        """Stop the example by closing the channel and connection. We
        set a flag here so that we stop scheduling new messages to be
        published. The IOLoop is started because this method is
        invoked by the Try/Catch below when KeyboardInterrupt is caught.
        Starting the IOLoop again will allow the publisher to cleanly
        disconnect from RabbitMQ.

        """
        self.my_local_logger.info('Stopping')
        self._stopping = True
        self.close_channel()
        self.close_connection()
        self.my_local_logger.info('Stopped')


def main():
    logging.basicConfig(level=logging.INFO, format=g_config.LOG_FORMAT)
    # connection_string='amqp://'+config.EON_MQ_UN+':'+config.EON_MQ_PW+'@'+config.EON_MQ_IP+':'+
    #               ('%d' % config.EON_MQ_PORT)+'/'+config.EON_MQ_BASE+'/'+config.EON_MQ_VHOST

    connection_string='amqp://' + g_config.EON_MQ_UN + ':' + g_config.EON_MQ_PW + '@' + \
                      g_config.EON_MQ_IP + ':' + ('%d' % g_config.EON_MQ_PORT) + '/' + g_config.EON_MQ_VHOST
    my_local_logger = logging.getLogger(__name__)

    my_local_logger.info("Connecting to %s" % connection_string)
    TEST_DISPATCH = False
    if TEST_DISPATCH:
        import Queue
        import eon_groomer
        # config.EON_MQ_IP='localhost'
        # config.EON_MQ_PORT=5672
        # config.EON_MQ_BASE='/#/queues'
        # config.EON_MQ_VHOST='eon360'
        # config.EON_MQ_QUEUE='collection-notification'
        # config.EON_MQ_UN='eon360'
        # config.EON_MQ_PW='eon360'

        # example = MQ_Dispatcher('amqp://guest:guest@localhost:5672/%2F')

        message_queue = Queue.Queue()
        queue_lock = threading.Lock()

        message_handler = eon_groomer.GroomingMessageHandler(message_queue, queue_lock)
        example = MqConsumer(connection_string,  message_handler, g_config.EON_GROOM_QUEUE)

        try:
            message_handler.start()
            example.run()
        except KeyboardInterrupt:
            example.stop()
            message_handler.join()
    else:
        import Queue
        message_queue = Queue.Queue()
        queue_lock = threading.Lock()
        example = MqPublisher(connection_string, message_queue, queue_lock, g_config.EON_GROOM_QUEUE)
        try:
            example.start()
            # example.run()
            i=0
            while i<50:
                i += 1
                print "i=%d" % i
                time.sleep(g_config.SLEEP_TIME)
            print "Setting up message now"
            # #############################################################
            # Setting up the QUEUE
            # #############################################################
            while not queue_lock.acquire(False):
                my_local_logger.info('MainTest:Pika bridge waiting to acquire lock.')
                time.sleep(g_config.SLEEP_TIME)
            my_local_logger.info('MainTest:Pika bridge acquired lock.')
            j = 0
            while j < 50:
                j += 1
                this_message = {"queryGuid": "4a1b34bc-9739-4b40-85e1-8f464fe98211",
                                "dateTime": "2015-05-03T19:42:33.689-0400",
                                "payload": {
                                    "zoomR": 1,
                                    "spatial": "[1,0; .2,.2; .3,.01]",
                                    "circuitID": "",
                                    "reputationEnabled": True,
                                    "assetID": "",
                                    "temporal": "[1,0; .8,24; .3, 60]",
                                    "outageTime": 1430452800000,
                                    "company": "CEDRAFT",
                                    "votes": 3,
                                    "zoomT": j,
                                    "longitude": -73.0,
                                    "latitude": 44.0,
                                    "radius": 0.12,
                                    "units": "MI"
                                },
                                "messageType": "Query"
                                }
                message_queue.put(this_message, False)
            queue_lock.release()

            # example.publish_message()
            print "Queued up 50 messages for publishing"
            while not message_queue.empty():
                print "waiting for queue to empty"
                time.sleep(g_config.SLEEP_TIME)
            i = 0
            while i < 50:
                i += 1
                print "second loop i=%d" % i
                time.sleep(g_config.SLEEP_TIME)
            example.stop()

        except KeyboardInterrupt:
            example.stop()
        example.join()

if __name__ == '__main__':
    main()
    print "finished tests"
