import re
import sys
import inspect
import logging

import yaml
from pbjson.pbjson import pb2dict
from pbjson.pbjson import dict2pb

import orwell.messages.controller_pb2
import orwell.messages.robot_pb2
import orwell.messages.server_game_pb2
import orwell.messages.server_web_pb2

import google.protobuf.descriptor as pb_descriptor


# adapted from http://stackoverflow.com/a/12144823/3552528
class CustomMetaClass(type):

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
        members['message'] = {}

        # make the actual object
        return meta(name, bases, members)

    def __init__(self, name, bases, members):
        for meta in self.combined_metas:
            meta.__init__(self, name, bases, members)


class Base(object):
    CAPTURE_PATTERN = re.compile('{[^{].*[^}]}')

    def __init__(self, payload, destination=None):
        self._message = self.PROTOBUF_CLASS()
        self._message.ParseFromString(payload)
        self.message = pb2dict(self._message)
        self.destination = destination

    def load(self):
        self._message = dict2pb(self.PROTOBUF_CLASS, self.message)

    @property
    def protobuf_message(self):
        if (not hasattr(self, '_message')):
            self.load()
        return self._message

    def __getattribute__(self, attribute):
        message = object.__getattribute__(self, "message")
        if ("message" == attribute):
            return message
        else:
            if (attribute in message):
                # this seems to never be visited but is kept just in case
                return message[attribute]
            else:
                return object.__getattribute__(self, attribute)

    def __repr__(self):
        return "%s(%s)" % (
            self.__class__.__name__,
            str(self.message),
        )

    @property
    def key_map(self):
        if (not hasattr(self, '_key_map')):
            path = []
            path_stack = [""]
            pb_stack = [self.protobuf_message]
            self._key_map = {}
            first = True
            while (pb_stack):
                message = pb_stack.pop()
                if (path_stack):
                    path.append(path_stack.pop())
                for field in message.ListFields():
                    descriptor, value = field
                    path.append(descriptor.name)
                    if (descriptor.type in
                            (pb_descriptor.FieldDescriptor.TYPE_GROUP,
                             pb_descriptor.FieldDescriptor.TYPE_MESSAGE)):
                        # nested message
                        pb_stack.append(value)
                        path_stack.append(path.pop())
                    else:
                        key = "/".join(path)
                        self._key_map[key] = value
                        path.pop()
                if (not first):
                    path.pop()
                else:
                    first = False
        return self._key_map



from collections import namedtuple
Comparison = namedtuple('Comparison', 'key reference_value compared')


class Capture(object):
    def __new__(cls, *args, **kwargs):
        instance = object.__new__(cls, *args, **kwargs)
        if (not hasattr(instance, 'arguments')):
            setattr(instance, 'arguments', {})
        setattr(instance, 'captured', [])
        setattr(instance, '_pb_message', None)
        # !CaptureMessage -> !Message
        setattr(
            instance,
            'captured_yaml_tag',
            instance.yaml_tag.replace('!Capture', '!'))
        return instance

    @staticmethod
    def create_from_zmq(zmq_message):
        destination, message_type, payload = zmq_message.split(' ', 2)
        found = False
        for module in (
                orwell.messages.controller_pb2,
                orwell.messages.robot_pb2,
                orwell.messages.server_game_pb2,
                orwell.messages.server_web_pb2):
            if (hasattr(module, message_type)):
                pb_klass = getattr(module, message_type)
                found = True
                break
        if (not found):
            raise Exception("Invalid message type: " + message_type)
        pb_message = pb_klass()
        pb_message.ParseFromString(payload)
        klass = getattr(sys.modules[__name__], "Capture" + message_type)
        capture = klass()
        capture._pb_message = pb_message
        capture.destination = destination
        capture.message = pb2dict(pb_message)
        logger = logging.getLogger(__name__)
        logger.debug("capture.message = " + str(capture.message))
        return capture

    @property
    def protobuf_message(self):
        if (self._pb_message is None):
            self._pb_message = self.fill(self.arguments)
            #self._pb_message = dict2pb(self.PROTOBUF_CLASS, self.message)
        return self._pb_message

    @property
    def key_map(self):
        if (not hasattr(self, '_key_map')):
            path = []
            path_stack = [""]
            dico_stack = [self.message]
            self._key_map = {}
            first = True
            while (dico_stack):
                dico = dico_stack.pop()
                if (path_stack):
                    path.append(path_stack.pop())
                for dico_key, value in dico.items():
                    path.append(dico_key)
                    if (isinstance(value, dict)):
                        # nested message
                        dico_stack.append(value)
                        path_stack.append(path.pop())
                    else:
                        key = "/".join(path)
                        self._key_map[key] = value
                        path.pop()
                if (not first):
                    path.pop()
                else:
                    first = False
        return self._key_map

    def encode_zmq_message(self, dico):
        if (('{' == self.destination[0]) and ('}' == self.destination[-1])):
            destination = self.destination.format(**dico)
        else:
            destination = self.destination
        return " ".join((
            destination,
            self.PROTOBUF_CLASS.DESCRIPTOR.name,
            self.fill(dico).SerializeToString()))

    def __getitem__(self, index):
        return self.captured[index]

    def __getattribute__(self, attribute):
        if (hasattr(self, "message")):
            message = object.__getattribute__(self, "message")
            if ("message" == attribute):
                return message
            else:
                if (attribute in message):
                    return message[attribute]
                else:
                    return object.__getattribute__(self, attribute)
        else:
            return object.__getattribute__(self, attribute)

    def compute_differences(self, other):
        differences = []
        captured = {}
        if (self.captured_yaml_tag != other.yaml_tag):
            differences.append(
                ("@name", self.captured_yaml_tag, other.yaml_tag))
        if (self.destination != other.destination):
            differences.append(
                ("@destination", self.destination, other.destination))

        comparisons = []
        for key, reference_value in self.key_map.items():
            comparison = Comparison(key, reference_value, other.key_map)
            comparisons.append(comparison)

        logger = logging.getLogger(__name__)
        while (comparisons):
            comparison = comparisons.pop(0)
            key = comparison.key
            reference_value = comparison.reference_value
            compared = comparison.compared
            logger.debug(
                "compute_differences - key = '{key}'"
                ", value = '{value}' "
                "; compared = '{compared}'".format(
                    key=key, value=reference_value, compared=compared))
            try:
                other_value = compared[key]
                if (isinstance(reference_value, dict)):
                    for sub_key, sub_value in reference_value.items():
                        comparisons.append(
                            Comparison(sub_key, sub_value, other_value))
                    continue
                elif (isinstance(reference_value, list)):
                    for sub, sub_other in zip(reference_value, other_value):
                        for sub_key, sub_value in sub.items():
                            comparisons.append(
                                Comparison(sub_key, sub_value, sub_other))
                    continue
            except:
                other_value = None
            logger.debug(
                    "compute_differences - key = '{key}'"
                    ", value = '{value}' "
                    "; other.key_map[key] = '{other_value}'".format(
                        key=key,
                        value=reference_value,
                        other_value=other_value))
            if (reference_value != other_value):
                if ((isinstance(reference_value, str)) and
                        (Base.CAPTURE_PATTERN.match(reference_value))):
                    capture_name = reference_value[1:-1]
                    captured[capture_name] = other_value
                else:
                    differences.append((key, reference_value, other_value))
        self.captured.append(captured)
        logger.debug("self")
        logger.debug(self)
        logger.debug("self.captured")
        logger.debug(self.captured)
        return differences

    def _compute_bool(self, value):
        return (value not in ("False", "false", 0))

    def _fill_list(
            self,
            translation_dico,
            key,
            value,
            destination_dico,
            descriptor,
            new_descriptor):
        new_element = []
        if (isinstance(destination_dico, dict)):
            destination_dico[key] = new_element
        elif (isinstance(destination_dico, list)):
            destination_dico.append(new_element)
        for sub_value in value:
            self._fill_one(
                translation_dico,
                new_descriptor.name,
                sub_value,
                new_element,
                descriptor)

    def _fill_dict(
            self,
            translation_dico,
            key,
            value,
            destination_dico,
            descriptor,
            new_descriptor):
        new_element = {}
        if (isinstance(destination_dico, dict)):
            destination_dico[key] = new_element
        elif (isinstance(destination_dico, list)):
            destination_dico.append(new_element)
        self._fill(
            translation_dico,
            value,
            new_element,
            new_descriptor)

    def _fill_value(
            self,
            translation_dico,
            key,
            value,
            destination_dico,
            descriptor,
            new_descriptor):
        if (isinstance(value, str)):
            value = value.format(**translation_dico)
        if (new_descriptor.type in
                (pb_descriptor.FieldDescriptor.TYPE_DOUBLE,
                 pb_descriptor.FieldDescriptor.TYPE_FLOAT)):
            value = float(value)
        elif (new_descriptor.type in
                (pb_descriptor.FieldDescriptor.TYPE_INT32,
                 pb_descriptor.FieldDescriptor.TYPE_SINT32,
                 pb_descriptor.FieldDescriptor.TYPE_UINT32,
                 pb_descriptor.FieldDescriptor.TYPE_FIXED32,
                 pb_descriptor.FieldDescriptor.TYPE_SFIXED32,
                 pb_descriptor.FieldDescriptor.TYPE_INT64,
                 pb_descriptor.FieldDescriptor.TYPE_SINT64,
                 pb_descriptor.FieldDescriptor.TYPE_UINT64,
                 pb_descriptor.FieldDescriptor.TYPE_FIXED64,
                 pb_descriptor.FieldDescriptor.TYPE_SFIXED64,
                 pb_descriptor.FieldDescriptor.TYPE_ENUM)):
            value = int(value)
        elif (pb_descriptor.FieldDescriptor.TYPE_BOOL
                == new_descriptor.type):
            value = self._compute_bool(value)
        if (isinstance(destination_dico, dict)):
            destination_dico[key] = value
        elif (isinstance(destination_dico, list)):
            destination_dico.append(value)

    def _fill_one(
            self,
            translation_dico,
            key,
            value,
            destination_dico,
            descriptor):
        if (isinstance(descriptor, pb_descriptor.Descriptor)):
            new_descriptor = descriptor.fields_by_name[key]
        else:
            new_descriptor = descriptor.message_type.fields_by_name[key]
        if (isinstance(value, list)):
            self._fill_list(
                translation_dico,
                key,
                value,
                destination_dico,
                descriptor,
                new_descriptor)
        elif (isinstance(value, dict)):
            self._fill_dict(
                translation_dico,
                key,
                value,
                destination_dico,
                descriptor,
                new_descriptor)
        else:
            self._fill_value(
                translation_dico,
                key,
                value,
                destination_dico,
                descriptor,
                new_descriptor)

    def _fill(
            self,
            translation_dico,
            source_dico,
            destination_dico,
            descriptor):
        for key, value in source_dico.items():
            self._fill_one(
                translation_dico,
                key,
                value,
                destination_dico,
                descriptor)

    def fill(self, dico):
        expanded_dico = {}
        logger = logging.getLogger(__name__)
        logger.debug("++ self.message %s\n" % (self.message))
        self._fill(
            dico,
            self.message,
            expanded_dico,
            self.PROTOBUF_CLASS.DESCRIPTOR)
        return dict2pb(self.PROTOBUF_CLASS, expanded_dico)


def get_classes_from_module(module):
    """ Extract module and name of classes.

    Simple version that does not deal with classes nested in other classes.
    """
    classes_and_modules = []
    class_descriptions = inspect.getmembers(module, inspect.isclass)
    for class_description in class_descriptions:
        name, klass = class_description
        module = klass.__module__
        classes_and_modules.append((name, module))
    return classes_and_modules


def configure_logging(verbose):
    logger = logging.getLogger(__name__)
    handler = logging.StreamHandler()
    logger.addHandler(handler)
    if (verbose):
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)


def generate():
    """Used to generate code with cog."""
    import orwell.messages.controller_pb2 as pb_controller
    import orwell.messages.robot_pb2 as pb_robot
    import orwell.messages.server_game_pb2 as pb_server_game
    import orwell.messages.server_web_pb2 as pb_server_web

    TEMPLATE = """
class {name}(yaml.YAMLObject, Base):
    __metaclass__ = CustomMetaClass
    PROTOBUF_CLASS = {module}.{name}
    yaml_tag = u'!{name}'


class Capture{name}(yaml.YAMLObject, Capture):
    PROTOBUF_CLASS = {module}.{name}
    yaml_tag = u'!Capture{name}'
    message_type = '{name}'

"""
    output = ""

    output += "\n"
    array = get_classes_from_module(pb_controller)
    array += get_classes_from_module(pb_robot)
    array += get_classes_from_module(pb_server_game)
    array += get_classes_from_module(pb_server_web)
    for class_name, module_name in array:
        output += TEMPLATE.format(name=class_name, module=module_name)
    return output


# use to generate the code with cog
# cog.py -r orwell/yaml2protobuf.py
# You may have to remove some classes before generating (you can remove
# all of them as they will be generated again).
COG_GENERATOR = """ [[[cog
import os
import sys
import inspect
full_path = os.path.abspath(inspect.getfile(inspect.currentframe()))
plus_index = full_path.rfind('+')
real_path = full_path[:plus_index]
print('exec(%s)' % real_path)
exec(open(real_path, 'r'))
import cog
cog.outl(generate())
# ]]] """


class Fire(yaml.YAMLObject, Base):
    __metaclass__ = CustomMetaClass
    PROTOBUF_CLASS = orwell.messages.controller_pb2.Fire
    yaml_tag = u'!Fire'


class CaptureFire(yaml.YAMLObject, Capture):
    PROTOBUF_CLASS = orwell.messages.controller_pb2.Fire
    yaml_tag = u'!CaptureFire'
    message_type = 'Fire'


class Hello(yaml.YAMLObject, Base):
    __metaclass__ = CustomMetaClass
    PROTOBUF_CLASS = orwell.messages.controller_pb2.Hello
    yaml_tag = u'!Hello'


class CaptureHello(yaml.YAMLObject, Capture):
    PROTOBUF_CLASS = orwell.messages.controller_pb2.Hello
    yaml_tag = u'!CaptureHello'
    message_type = 'Hello'


class Input(yaml.YAMLObject, Base):
    __metaclass__ = CustomMetaClass
    PROTOBUF_CLASS = orwell.messages.controller_pb2.Input
    yaml_tag = u'!Input'


class CaptureInput(yaml.YAMLObject, Capture):
    PROTOBUF_CLASS = orwell.messages.controller_pb2.Input
    yaml_tag = u'!CaptureInput'
    message_type = 'Input'


class Move(yaml.YAMLObject, Base):
    __metaclass__ = CustomMetaClass
    PROTOBUF_CLASS = orwell.messages.controller_pb2.Move
    yaml_tag = u'!Move'


class CaptureMove(yaml.YAMLObject, Capture):
    PROTOBUF_CLASS = orwell.messages.controller_pb2.Move
    yaml_tag = u'!CaptureMove'
    message_type = 'Move'


class Ping(yaml.YAMLObject, Base):
    __metaclass__ = CustomMetaClass
    PROTOBUF_CLASS = orwell.messages.controller_pb2.Ping
    yaml_tag = u'!Ping'


class CapturePing(yaml.YAMLObject, Capture):
    PROTOBUF_CLASS = orwell.messages.controller_pb2.Ping
    yaml_tag = u'!CapturePing'
    message_type = 'Ping'


class Colour(yaml.YAMLObject, Base):
    __metaclass__ = CustomMetaClass
    PROTOBUF_CLASS = orwell.messages.robot_pb2.Colour
    yaml_tag = u'!Colour'


class CaptureColour(yaml.YAMLObject, Capture):
    PROTOBUF_CLASS = orwell.messages.robot_pb2.Colour
    yaml_tag = u'!CaptureColour'
    message_type = 'Colour'


class Pong(yaml.YAMLObject, Base):
    __metaclass__ = CustomMetaClass
    PROTOBUF_CLASS = orwell.messages.robot_pb2.Pong
    yaml_tag = u'!Pong'


class CapturePong(yaml.YAMLObject, Capture):
    PROTOBUF_CLASS = orwell.messages.robot_pb2.Pong
    yaml_tag = u'!CapturePong'
    message_type = 'Pong'


class Register(yaml.YAMLObject, Base):
    __metaclass__ = CustomMetaClass
    PROTOBUF_CLASS = orwell.messages.robot_pb2.Register
    yaml_tag = u'!Register'


class CaptureRegister(yaml.YAMLObject, Capture):
    PROTOBUF_CLASS = orwell.messages.robot_pb2.Register
    yaml_tag = u'!CaptureRegister'
    message_type = 'Register'


class Rfid(yaml.YAMLObject, Base):
    __metaclass__ = CustomMetaClass
    PROTOBUF_CLASS = orwell.messages.robot_pb2.Rfid
    yaml_tag = u'!Rfid'


class CaptureRfid(yaml.YAMLObject, Capture):
    PROTOBUF_CLASS = orwell.messages.robot_pb2.Rfid
    yaml_tag = u'!CaptureRfid'
    message_type = 'Rfid'


class ServerRobotState(yaml.YAMLObject, Base):
    __metaclass__ = CustomMetaClass
    PROTOBUF_CLASS = orwell.messages.robot_pb2.ServerRobotState
    yaml_tag = u'!ServerRobotState'


class CaptureServerRobotState(yaml.YAMLObject, Capture):
    PROTOBUF_CLASS = orwell.messages.robot_pb2.ServerRobotState
    yaml_tag = u'!CaptureServerRobotState'
    message_type = 'ServerRobotState'


class Access(yaml.YAMLObject, Base):
    __metaclass__ = CustomMetaClass
    PROTOBUF_CLASS = orwell.messages.server_game_pb2.Access
    yaml_tag = u'!Access'


class CaptureAccess(yaml.YAMLObject, Capture):
    PROTOBUF_CLASS = orwell.messages.server_game_pb2.Access
    yaml_tag = u'!CaptureAccess'
    message_type = 'Access'


class Battery(yaml.YAMLObject, Base):
    __metaclass__ = CustomMetaClass
    PROTOBUF_CLASS = orwell.messages.common_pb2.Battery
    yaml_tag = u'!Battery'


class CaptureBattery(yaml.YAMLObject, Capture):
    PROTOBUF_CLASS = orwell.messages.common_pb2.Battery
    yaml_tag = u'!CaptureBattery'
    message_type = 'Battery'


class Coordinates(yaml.YAMLObject, Base):
    __metaclass__ = CustomMetaClass
    PROTOBUF_CLASS = orwell.messages.server_game_pb2.Coordinates
    yaml_tag = u'!Coordinates'


class CaptureCoordinates(yaml.YAMLObject, Capture):
    PROTOBUF_CLASS = orwell.messages.server_game_pb2.Coordinates
    yaml_tag = u'!CaptureCoordinates'
    message_type = 'Coordinates'


class GameState(yaml.YAMLObject, Base):
    __metaclass__ = CustomMetaClass
    PROTOBUF_CLASS = orwell.messages.server_game_pb2.GameState
    yaml_tag = u'!GameState'


class CaptureGameState(yaml.YAMLObject, Capture):
    PROTOBUF_CLASS = orwell.messages.server_game_pb2.GameState
    yaml_tag = u'!CaptureGameState'
    message_type = 'GameState'


class Goodbye(yaml.YAMLObject, Base):
    __metaclass__ = CustomMetaClass
    PROTOBUF_CLASS = orwell.messages.server_game_pb2.Goodbye
    yaml_tag = u'!Goodbye'


class CaptureGoodbye(yaml.YAMLObject, Capture):
    PROTOBUF_CLASS = orwell.messages.server_game_pb2.Goodbye
    yaml_tag = u'!CaptureGoodbye'
    message_type = 'Goodbye'


class Item(yaml.YAMLObject, Base):
    __metaclass__ = CustomMetaClass
    PROTOBUF_CLASS = orwell.messages.server_game_pb2.Item
    yaml_tag = u'!Item'


class CaptureItem(yaml.YAMLObject, Capture):
    PROTOBUF_CLASS = orwell.messages.server_game_pb2.Item
    yaml_tag = u'!CaptureItem'
    message_type = 'Item'


class Landmark(yaml.YAMLObject, Base):
    __metaclass__ = CustomMetaClass
    PROTOBUF_CLASS = orwell.messages.server_game_pb2.Landmark
    yaml_tag = u'!Landmark'


class CaptureLandmark(yaml.YAMLObject, Capture):
    PROTOBUF_CLASS = orwell.messages.server_game_pb2.Landmark
    yaml_tag = u'!CaptureLandmark'
    message_type = 'Landmark'


class PlayerState(yaml.YAMLObject, Base):
    __metaclass__ = CustomMetaClass
    PROTOBUF_CLASS = orwell.messages.server_game_pb2.PlayerState
    yaml_tag = u'!PlayerState'


class CapturePlayerState(yaml.YAMLObject, Capture):
    PROTOBUF_CLASS = orwell.messages.server_game_pb2.PlayerState
    yaml_tag = u'!CapturePlayerState'
    message_type = 'PlayerState'


class RGBColour(yaml.YAMLObject, Base):
    __metaclass__ = CustomMetaClass
    PROTOBUF_CLASS = orwell.messages.server_game_pb2.RGBColour
    yaml_tag = u'!RGBColour'


class CaptureRGBColour(yaml.YAMLObject, Capture):
    PROTOBUF_CLASS = orwell.messages.server_game_pb2.RGBColour
    yaml_tag = u'!CaptureRGBColour'
    message_type = 'RGBColour'


class Registered(yaml.YAMLObject, Base):
    __metaclass__ = CustomMetaClass
    PROTOBUF_CLASS = orwell.messages.server_game_pb2.Registered
    yaml_tag = u'!Registered'


class CaptureRegistered(yaml.YAMLObject, Capture):
    PROTOBUF_CLASS = orwell.messages.server_game_pb2.Registered
    yaml_tag = u'!CaptureRegistered'
    message_type = 'Registered'


class Start(yaml.YAMLObject, Base):
    __metaclass__ = CustomMetaClass
    PROTOBUF_CLASS = orwell.messages.server_game_pb2.Start
    yaml_tag = u'!Start'


class CaptureStart(yaml.YAMLObject, Capture):
    PROTOBUF_CLASS = orwell.messages.server_game_pb2.Start
    yaml_tag = u'!CaptureStart'
    message_type = 'Start'


class Stop(yaml.YAMLObject, Base):
    __metaclass__ = CustomMetaClass
    PROTOBUF_CLASS = orwell.messages.server_game_pb2.Stop
    yaml_tag = u'!Stop'


class CaptureStop(yaml.YAMLObject, Capture):
    PROTOBUF_CLASS = orwell.messages.server_game_pb2.Stop
    yaml_tag = u'!CaptureStop'
    message_type = 'Stop'


class Team(yaml.YAMLObject, Base):
    __metaclass__ = CustomMetaClass
    PROTOBUF_CLASS = orwell.messages.server_game_pb2.Team
    yaml_tag = u'!Team'


class CaptureTeam(yaml.YAMLObject, Capture):
    PROTOBUF_CLASS = orwell.messages.server_game_pb2.Team
    yaml_tag = u'!CaptureTeam'
    message_type = 'Team'


class Timing(yaml.YAMLObject, Base):
    __metaclass__ = CustomMetaClass
    PROTOBUF_CLASS = orwell.messages.common_pb2.Timing
    yaml_tag = u'!Timing'


class CaptureTiming(yaml.YAMLObject, Capture):
    PROTOBUF_CLASS = orwell.messages.common_pb2.Timing
    yaml_tag = u'!CaptureTiming'
    message_type = 'Timing'


class Ultrasound(yaml.YAMLObject, Base):
    __metaclass__ = CustomMetaClass
    PROTOBUF_CLASS = orwell.messages.common_pb2.Ultrasound
    yaml_tag = u'!Ultrasound'


class CaptureUltrasound(yaml.YAMLObject, Capture):
    PROTOBUF_CLASS = orwell.messages.common_pb2.Ultrasound
    yaml_tag = u'!CaptureUltrasound'
    message_type = 'Ultrasound'


class Welcome(yaml.YAMLObject, Base):
    __metaclass__ = CustomMetaClass
    PROTOBUF_CLASS = orwell.messages.server_game_pb2.Welcome
    yaml_tag = u'!Welcome'


class CaptureWelcome(yaml.YAMLObject, Capture):
    PROTOBUF_CLASS = orwell.messages.server_game_pb2.Welcome
    yaml_tag = u'!CaptureWelcome'
    message_type = 'Welcome'


class GetAccess(yaml.YAMLObject, Base):
    __metaclass__ = CustomMetaClass
    PROTOBUF_CLASS = orwell.messages.server_web_pb2.GetAccess
    yaml_tag = u'!GetAccess'


class CaptureGetAccess(yaml.YAMLObject, Capture):
    PROTOBUF_CLASS = orwell.messages.server_web_pb2.GetAccess
    yaml_tag = u'!CaptureGetAccess'
    message_type = 'GetAccess'


class GetGameState(yaml.YAMLObject, Base):
    __metaclass__ = CustomMetaClass
    PROTOBUF_CLASS = orwell.messages.server_web_pb2.GetGameState
    yaml_tag = u'!GetGameState'


class CaptureGetGameState(yaml.YAMLObject, Capture):
    PROTOBUF_CLASS = orwell.messages.server_web_pb2.GetGameState
    yaml_tag = u'!CaptureGetGameState'
    message_type = 'GetGameState'


# [[[end]]]

if ("__main__" == __name__):
    print(generate())
