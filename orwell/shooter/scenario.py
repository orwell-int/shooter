from .. import yaml2protobuf
import yaml
import zmq
import collections
import re
import time
import logging


class Socket(object):
    """Base class for zmq socket wrappers.

    This should not be instantiated but contains some methods common to
    the derived classes.
    """

    @property
    def connection_string(self):
        bind = getattr(self, 'bind', False)
        protocol = getattr(self, 'protocol', "tcp")
        if (bind):
            address = getattr(self, 'address', "0.0.0.0")
        else:
            address = getattr(self, 'address', "127.0.0.1")
        return "%s://%s:%i" % (protocol, address, self.port)

    @property
    def mode(self):
        if (zmq.PUSH == self.zmq_method):
            return "push"
        if (zmq.PULL == self.zmq_method):
            return "pull"
        if (zmq.PUB == self.zmq_method):
            return "publish"
        if (zmq.SUB == self.zmq_method):
            return "subsccribe"

    def build(self, zmq_context):
        logger = logging.getLogger(__name__)
        bind = getattr(self, 'bind', False)
        self.bind = bind
        self._zmq_socket = zmq_context.socket(self.zmq_method)
        self._zmq_socket.setsockopt(zmq.LINGER, 1)
        if (bind):
            logger.info(
                "Bind on " + self.connection_string + " " + self.mode)
            self._zmq_socket.bind(self.connection_string)
        else:
            logger.info(
                "Connect to " + self.connection_string + " " + self.mode)
            self._zmq_socket.connect(self.connection_string)

    def __repr__(self):
        return "{%s | %s}" % (self.yaml_tag[1:], self.connection_string)

    def terminate(self):
        if (self.bind):
            self._zmq_socket.unbind(self.connection_string)
        else:
            self._zmq_socket.disconnect(self.connection_string)
        self._zmq_socket.close()


class SocketPull(yaml.YAMLObject, Socket):
    """To be used in YAML.

    Wrapper for zmq pull socket.
    """

    yaml_tag = u'!SocketPull'
    zmq_method = zmq.PULL

    def recv(self, *args, **kwargs):
        event = self._zmq_socket.poll(10)
        if (zmq.POLLIN == event):
            return self._zmq_socket.recv(*args, **kwargs)
        else:
            return None


class SocketPush(yaml.YAMLObject, Socket):

    """To be used in YAML.

    Wrapper for zmq push socket.
    """

    yaml_tag = u'!SocketPush'
    zmq_method = zmq.PUSH

    def send(self, data):
        logger = logging.getLogger(__name__)
        logger.info("SocketPush.send({})".format(repr(data)))
        self._zmq_socket.send(data)


class SocketSubscribe(yaml.YAMLObject, Socket):
    """To be used in YAML.

    Wrapper for zmq sub socket.
    """

    yaml_tag = u'!SocketSubscribe'
    zmq_method = zmq.SUB

    def build(self, zmq_context):
        super(self.__class__, self).build(zmq_context)
        self._zmq_socket.setsockopt(zmq.SUBSCRIBE, "")

    def recv(self, *args, **kwargs):
        event = self._zmq_socket.poll(10)
        logger = logging.getLogger(__name__)
        logger.debug("event = " + str(event))
        if (zmq.POLLIN == event):
            return self._zmq_socket.recv(*args, **kwargs)
        else:
            return None


class SocketPublish(yaml.YAMLObject, Socket):
    """To be used in YAML.

    Wrapper for zmq publish socket.
    """

    yaml_tag = u'!SocketPublish'
    zmq_method = zmq.PUB

    def send(self, data):
        logger = logging.getLogger(__name__)
        logger.info("SocketPublish.send({})".format(repr(data)))
        self._zmq_socket.send(data)


class ExchangeMetaClass(type):
    """Metaclass to combine YAMLObject and base class Exchange.

    adapted from http://stackoverflow.com/a/12144823/3552528
    """

    def __new__(cls, name, bases, members):
        #collect up the metaclasses
        metas = [type(base) for base in bases]

        # prune repeated or conflicting entries
        metas = [meta for index, meta in enumerate(metas)
                 if not [later for later in metas[index+1:]
                         if issubclass(later, meta)]]

        # whip up the actual combined meta class derive off all of these
        meta = type(name, tuple(metas), dict(combined_metas=metas))

        # the member is added here because the constructor does not get
        # called when the objects are constructed from yaml.
        if ("arguments" not in members):
            members["arguments"] = {}

        # make the actual object
        return meta(name, bases, members)

    def __init__(self, name, bases, members):
        for meta in self.combined_metas:
            meta.__init__(self, name, bases, members)


class Exchange(object):
    """Base class for exchanges which are about sending or receiving messages.

    This should not be instantiated but contains some methods common to
    the derived classes.
    """

    def __repr__(self):
        return "{%s | message: %s ; arguments: %s}" % (
            self.yaml_tag,
            str(self.message.yaml_tag),
            str(self.arguments))

    def build(self, repository, in_socket, out_socket):
        self._in_socket = in_socket
        self._out_socket = out_socket
        self._repository = repository


class In(yaml.YAMLObject, Exchange):
    """To be used in YAML.

    Class to receive messages in a thread.
    """

    __metaclass__ = ExchangeMetaClass
    yaml_tag = u'!In'

    def step(self):
        logger = logging.getLogger(__name__)
        logger.debug("In.step")
        try:
            zmq_message = self._in_socket.recv()
        except Exception as ex:
            logger.warning("Exception in In.step:" + str(ex))
            zmq_message = None
        if (zmq_message):
            logger.info("received zmq message %s" % repr(zmq_message))
            message = yaml2protobuf.Capture.create_from_zmq(zmq_message)
            if (message.message_type != self.message.message_type):
                zmq_message = None
            else:
                self.message.destination = message.destination
                self.message.raw = message._pb_message
                # print("type(self.message) = " + str(type(self.message)))
                # print("id(self.message) = " + str(hex(id(self.message))))
                differences = self.message.compute_differences(message)
                logger.info("differences = " + str(differences))
                # @TODO: implement exact match
                if (differences):
                    # zmq_message = None
                    pass
                # else:
                self._repository.add_received_message(self.message)
        return zmq_message, zmq_message is not None


class Out(yaml.YAMLObject, Exchange):
    """To be used in YAML.

    Class to send messages in a thread.
    """

    __metaclass__ = ExchangeMetaClass
    yaml_tag = u'!Out'
    arguments = {}

    def build(self, repository, in_socket, out_socket):
        super(self.__class__, self).build(repository, in_socket, out_socket)

    def step(self):
        logger = logging.getLogger(__name__)
        logger.info("Out.step")
        logger.debug("arguments = " + str(self.arguments))
        expanded_arguments = {key: self._repository.expand(value)
                              for key, value in self.arguments.items()}
        logger.debug("expanded arguments = " + str(expanded_arguments))
        self._out_socket.send(
            self.message.encode_zmq_message(expanded_arguments))
        return None, True


class Equal(yaml.YAMLObject):
    """To be used in YAML.

    Class to assert that some given values are equal.
    """

    yaml_tag = u'!Equal'

    def build(self, repository, in_socket, out_socket):
        self._repository = repository
        values_count = len(self.values)
        if (values_count < 2):
            raise Exception(
                "Only {} value(s) found but 2 expected.".format(values_count))

    def step(self, *args):
        logger = logging.getLogger(__name__)
        logger.info("Equal.step")
        reference = None
        all_equal = True
        for value in self.values:
            value = self._repository.expand(value)
            if (reference is None):
                reference = value
            else:
                if (reference != value):
                    logger.warning(
                        "Values differ: " + str(reference) + " " + str(value))
                    all_equal = False
                    break
        return (all_equal, True)

    def __repr__(self):
        return "{Equal | %s}" % str(self.values)


class Absent(yaml.YAMLObject):
    """To be used in YAML.

    Class to assert that an object does not contain something.
    """

    yaml_tag = u'!Absent'

    def build(self, repository, in_socket, out_socket):
        self._repository = repository
        values_count = len(self.values)
        if (values_count < 2):
            raise Exception(
                "Only {} value(s) found but 2 expected.".format(values_count))

    def step(self, *args):
        logger = logging.getLogger(__name__)
        logger.info("Absent.step")
        reference = None
        absent = True
        for value in self.values:
            value = self._repository.expand(value)
            if (reference is None):
                reference = value
            else:
                if (value in reference):
                    logger.warning("Absent not verified:", reference, value)
                    absent = False
                    break
        return (absent, True)

    def __repr__(self):
        return "{Absent | %s}" % str(self.values)


class CaptureConverter(object):
    """Converts the format of yaml2protobuf.CaptureXXX.captured.

    The only used should be in CaptureRepository to have an easy syntax to
    evaluate user provided expressions to manipulate values captured in
    received messages.
    """

    def __init__(self, capture_list, destination=None, raw=None):
        self._values = {}
        self.raw = raw
        logger = logging.getLogger(__name__)
        logger.debug("capture_list")
        logger.debug(capture_list)
        for dico in capture_list:
            for key, value in dico.items():
                if (key in self._values):
                    #raise Exception("Duplicate key: '" + key + "'")
                    # we reuse the same object when we loop
                    # @TODO: possibly clear the object
                    pass
                self._values[key] = value
        if (destination is not None):
            self.destination = destination

    def __getattr__(self, attribute):
        if (attribute in self._values):
            return self._values[attribute]
        else:
            raise AttributeError(
                "'CaptureConverter' object has no attribute '%s'" % attribute)


class CaptureRepository(object):
    """Deals with values extracted from captures in received messages.

    Warning: there is an unsafe eval performed.
    """

    eval_regexp = re.compile(r'\{[^{].*[^}]\}')

    def __init__(self):
        self._values_from_received_messages = collections.defaultdict(list)

    def add_received_message(self, message):
        # message is of type CaptureXXX
        # print("CaptureRepository::add_received_message(" + str(type(message)) + "@" + str(hex(id(message)))) + ")"
        capture_converter = CaptureConverter(
                message.captured,
                message.destination,
                message.raw)
        # print("capture_converter = " + str(capture_converter))
        self._values_from_received_messages[message.message_type].append(
            capture_converter)

    def expand(self, string):
        logger = logging.getLogger(__name__)
        logger.debug("string = '" + repr(string) + "'")
        logger.debug("type(string) = '" + str(type(string)) + "'")
        if ((isinstance(string, str)) and
                (CaptureRepository.eval_regexp.match(string))):
            string_without_brackets = string[1:-1]
            logger.debug(
                "string_without_brackets = '" + string_without_brackets + "'")
            value = str(eval(
                string_without_brackets,
                self._values_from_received_messages))
            logger.debug("expanded string to value='" + value + "'")
        else:
            value = string
            logger.debug("copied string to value='" + str(value) + "'")
        return value


class Thread(yaml.YAMLObject):
    """To be used in YAML.

    Class to describe a succession of steps to be executed in sequence.
    """

    yaml_tag = u'!Thread'

    def build(self, zmq_context):
        self.in_socket.build(zmq_context)
        self.out_socket.build(zmq_context)
        self._repository = CaptureRepository()
        for element in self.flow:
            element.build(self._repository, self.in_socket, self.out_socket)
        if (not hasattr(self, "index")):
            self.index = 0

    def step(self):
        logger = logging.getLogger(__name__)
        if (self.has_more_steps):
            logger.debug("In thread '{name}' at step {index}".format(
                name=self.name, index=self.index))
            result, inc = self.flow[self.index].step()
            logger.debug(
                "In thread '{name}': "
                "index = {index} ; result = {result} ; inc = {inc}".format(
                    name=self.name,
                    index=self.index,
                    result=repr(result),
                    inc=inc))
            if (result is not None and not result):
                error_message = "Failure at index {} in thread '{}'.".format(
                        self.index, self.name)
                raise Exception(error_message)
            if (inc):
                self.index = (self.index + 1)
                if (self.loop):
                    self.index %= len(self.flow)
        else:
            logger.info("Skipped thread '{name}'".format(name=self.name))

    @property
    def has_more_steps(self):
        return (self.index < len(self.flow))

    def terminate(self):
        self.in_socket.terminate()
        self.out_socket.terminate()

    def __repr__(self):
        return "{Thread | in_socket = %s ; out_socket = %s ; flow = %s}" % (
            str(self.in_socket),
            str(self.out_socket),
            str(self.flow)
            )


class Scenario(object):
    """Class that the clients of this module need to use in their code.

    The other classes are only helping build a scenario in YAML which is
    wrapped by this class.
    This is implemented as a context manager so that users do not have to
    remember to call terminate when done to clean zmq objects.
    """

    def __init__(self, yaml_content):
        self._data = yaml.load(yaml_content)
        self._messages = self._data["messages"]
        self._zmq_context = zmq.Context()
        self._threads = self._data["threads"]

    def build(self):
        for thread in self._threads:
            thread.build(self._zmq_context)

    def step(self):
        for thread in self._threads:
            thread.step()

    def step_all(self):
        while (self.has_more_steps):
            self.step()

    @property
    def has_more_steps(self):
        return any((thread.has_more_steps for thread in self._threads))

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        self.terminate()

    def terminate(self):
        for thread in self._threads:
            thread.terminate()
        self._zmq_context.term()


class Sleep(yaml.YAMLObject):
    """To be used in YAML.

    Class to sleep for a given amount of seconds.
    """

    yaml_tag = u'!Sleep'

    def build(self, repository, in_socket, out_socket):
        pass

    def step(self, *args):
        logger = logging.getLogger(__name__)
        logger.info("Sleep.step")
        time.sleep(self.seconds)
        return (None, True)

    def __repr__(self):
        return "{Sleep | %ss}" % str(self.seconds)


class UserInput(yaml.YAMLObject):
    """To be used in YAML.

    Class to wait until the user provide some input.
    """

    yaml_tag = u'!UserInput'

    def build(self, repository, in_socket, out_socket):
        pass

    def step(self, *args):
        logger = logging.getLogger(__name__)
        logger.info("UserInput.step")
        raw_input(self.text)
        return (None, True)

    def __repr__(self):
        return "{UserInput}"


def configure_logging(verbose):
    logger = logging.getLogger(__name__)
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
            '%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    if (verbose):
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    yaml2protobuf.configure_logging(verbose)
