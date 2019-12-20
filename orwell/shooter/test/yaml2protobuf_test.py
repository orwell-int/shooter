from nose.tools import assert_equal
import unittest
import orwell.yaml2protobuf as y2p
import sys
import yaml
import orwell.messages.controller_pb2 as pb_controller
import orwell.messages.robot_pb2 as pb_robot
import orwell.messages.server_game_pb2 as pb_server_game
from pbjson.pbjson import pb2dict
from pbjson.pbjson import dict2pb


class MainTest(unittest.TestCase):
    @staticmethod
    def test_1():
        """Simple test with default value."""
        name = "Test"
        yaml_content = """
message: !CaptureHello
    message:
        name: {name}
""".format(name=name)
        data = yaml.load(yaml_content)
        hello = data["message"]
        assert_equal(hello.name, name)
        payload = hello.protobuf_message.SerializeToString()
        message2 = pb_controller.Hello()
        message2.ParseFromString(payload)
        assert_equal(name, message2.name)
        assert_equal(True, message2.ready)

    def test_2(self):
        """Simple test with default value overriden."""
        name = "Test"
        ready = False
        yaml_content = """
message: !CaptureHello
    message:
        name: {name}
        ready: {ready}
""".format(name=name, ready=ready)
        data = yaml.load(yaml_content)
        hello = data["message"]
        assert_equal(hello.name, name)
        payload = hello.protobuf_message.SerializeToString()
        message2 = pb_controller.Hello()
        message2.ParseFromString(payload)
        assert_equal(name, message2.name)
        assert_equal(ready, message2.ready)

    def test_3(self):
        """Play with the underlying library (not really a test)."""
        message = pb_controller.Hello()
        name = "JAMBON"
        message.name = name
        dico = pb2dict(message)
        message = pb_controller.Input()
        left = 0.2
        right = -0.5
        weapon1 = False
        weapon2 = True
        message.move.left = left
        message.move.right = right
        message.fire.weapon1 = weapon1
        message.fire.weapon2 = weapon2
        dico = pb2dict(message)
        message2 = dict2pb(pb_controller.Input, dico)
        assert_equal(left, message2.move.left)
        assert_equal(right, message2.move.right)
        assert_equal(weapon1, message2.fire.weapon1)
        assert_equal(weapon2, message2.fire.weapon2)

    def test_4(self):
        """Nested message."""
        message = pb_controller.Input()
        message.move.left = 0.2
        message.move.right = -0.5
        message.fire.weapon1 = False
        message.fire.weapon2 = True
        yaml_content = """
message: !CaptureInput
    message:
        move:
            left: {left}
            right: {right}
        fire:
            weapon1: {weapon1}
            weapon2: {weapon2}
""".format(
            left=message.move.left,
            right=message.move.right,
            weapon1=message.fire.weapon1,
            weapon2=message.fire.weapon2)
        data = yaml.load(yaml_content)
        message2 = data["message"]
        assert_equal(message.move.left, message2.protobuf_message.move.left)
        assert_equal(message.move.right, message2.protobuf_message.move.right)
        assert_equal(message.fire.weapon1,
                     message2.protobuf_message.fire.weapon1)
        assert_equal(message.fire.weapon2,
                     message2.protobuf_message.fire.weapon2)

    def test_5(self):
        """Use the inline notation (json like)"""
        message = pb_controller.Input()
        message.move.left = 0.2
        message.move.right = -0.5
        message.fire.weapon1 = False
        message.fire.weapon2 = True
        yaml_content = """
message: !CaptureInput {{ "message": {{ "move": {{ "left": {left},
"right": {right} }}, "fire": {{ "weapon1": {weapon1}, "weapon2": {weapon2} }}
}} }}""".format(
            left=message.move.left,
            right=message.move.right,
            weapon1=message.fire.weapon1,
            weapon2=message.fire.weapon2)
        data = yaml.load(yaml_content)
        message2 = data["message"]
        assert_equal(message.move.left, message2.protobuf_message.move.left)
        assert_equal(message.move.right, message2.protobuf_message.move.right)
        assert_equal(message.fire.weapon1,
                     message2.protobuf_message.fire.weapon1)
        assert_equal(message.fire.weapon2,
                     message2.protobuf_message.fire.weapon2)

    def not_a_test_6(self):
        """Implemented to see how the libraries work. There are no assertions.
        """
        import os
        test_dir = os.path.dirname(os.path.realpath(__file__))
        with open(os.path.join(test_dir, "conf.yaml"), 'r') as input:
            data = yaml.load(input.read())
            sys.stderr.write(str(data) + "\n")
            for dico in data["messages"]:
                #sys.stderr.write(" " + str(dico) + "\n")
                for name, message in dico.items():
                    sys.stderr.write("  " + str(name) + "\n")
                    sys.stderr.write(
                        "  pb fields: " +
                        str(message.protobuf_message.ListFields()) + "\n")
                    sys.stderr.write("  pb:\n")
                    sys.stderr.write(
                        "   " + "\n   ".join(
                            str(message.protobuf_message).split("\n")) + "\n")
                    if "register" == name:
                        message_register_in = message.protobuf_message
                    sys.stderr.write(
                        "   extracted = " + str(message.key_map) + "\n")
        message_register = pb_robot.Register()
        message_register.temporary_robot_id = "TEMPID1"
        message_register.video_url = "http://video.url:123"
        message_register.image = "this is an image of the robot"
        sys.stderr.write(str(message_register) + "\n")
        sys.stderr.write(str(dir(message_register)) + "\n")
        sys.stderr.write(
            "fields: " + str(message_register.ListFields()) + "\n")
        sys.stderr.write(str(message_register == message_register_in) + "\n")
        sys.stderr.write(" " + str(message_register.temporary_robot_id) + "\n")
        sys.stderr.write(" " + str(message_register.video_url) + "\n")
        sys.stderr.write(" " + str(message_register.image) + "\n")
        message_registered = pb_server_game.Registered()
        message_registered.robot_id = "ROBOT1"
        message_registered.team = "RED"
        sys.stderr.write(str(message_registered) + "\n")
        sys.stderr.write(" " + str(message_registered.robot_id) + "\n")
        sys.stderr.write(" " + str(message_registered.team) + "\n")

    @staticmethod
    def test_key_map():
        pb_message = pb_controller.Input()
        left = 0.2
        right = 0.5
        pb_message.move.left = left
        pb_message.move.right = right
        pb_message.fire.weapon1 = False
        pb_message.fire.weapon2 = True
        yaml_content = """
message: !CaptureInput
    destination: TEST1
    message:
        move:
            left: {left}
            right: "{{right}}"
        fire:
            weapon1: {weapon1}
            weapon2: {weapon2}
""".format(
            left=pb_message.move.left,
            weapon1=pb_message.fire.weapon1,
            weapon2=pb_message.fire.weapon2)
        data = yaml.load(yaml_content)
        message1 = data["message"]
        sys.stderr.write("\n" + str(message1.key_map) + "\n")
        assert_equal(message1.key_map["/move/left"], pb_message.move.left)
        assert_equal(message1.key_map["/move/right"], '{right}')
        assert_equal(message1.key_map["/fire/weapon1"],
                     pb_message.fire.weapon1)
        assert_equal(message1.key_map["/fire/weapon2"],
                     pb_message.fire.weapon2)
        new_left = 1.0
        pb_message.move.left = new_left
        message2 = y2p.Input(pb_message.SerializeToString())
        sys.stderr.write(str(message2.key_map) + "\n")
        assert_equal(message2.key_map["/move/left"], pb_message.move.left)
        assert_equal(message2.key_map["/move/right"], pb_message.move.right)
        assert_equal(message2.key_map["/fire/weapon1"],
                     pb_message.fire.weapon1)
        assert_equal(message2.key_map["/fire/weapon2"],
                     pb_message.fire.weapon2)
        diffs = message1.compute_differences(message2)
        sys.stderr.write(str(diffs) + "\n")
        # the name differs because we did not go thourgh the standard path
        # that removes the Capture part in the name.
        assert_equal(
            [('@name', u'!CaptureInput', u'!Input'),
             ('@destination', 'TEST1', None),
             ('/move/left', left, new_left)],
            diffs)
        sys.stderr.write(str(message1.captured) + "\n")
        assert_equal([{'right': right}], message1.captured)
        pb_message = message1.fill(message1.captured[-1])
        sys.stderr.write('filled:' + str(pb_message) + "\n")
        message2.protobuf_message.move.left = left
        assert_equal(str(pb_message), str(message2.protobuf_message))
        assert_equal(pb_message, message2.protobuf_message)


class CaptureTest(unittest.TestCase):
    @staticmethod
    def test_create_from_zmq():
        fake_message_type = "FakeMessageType"
        try:
            y2p.Capture.create_from_zmq("destination {} payload".format(
                fake_message_type))
        except Exception as exception:
            expected = Exception("Invalid message type: " + fake_message_type)
            assert_equal(repr(expected), repr(exception))

    @staticmethod
    def test_create_from_zmq_with_list():
        destination = "fake_id"
        playing = '"false"'
        seconds = 42
        yaml_content = """
message: !CaptureGameState
    destination: "{destination}"
    message:
        playing: {playing}
        seconds: {seconds}
        teams:
            - name: "{{looser_team}}"
              score: 0
              num_players: 2
              players:
                  - "looser_robot 1"
                  - "looser_robot 2"
            - name: "{{winner_team}}"
              score: 0
              num_players: 2
              players:
                  - "winner_robot 1"
                  - "{{winner_robot_two}}"
""".format(
            destination=destination,
            playing=playing,
            seconds=seconds)
        data = yaml.load(yaml_content)
        message = data["message"]
        looser_team = "Loosers"
        winner_team = "Winners"
        winner_robot_two = "winner robot 2"
        zmq_message = message.encode_zmq_message(
            {'looser_team': looser_team,
             'winner_team': winner_team,
             'winner_robot_two': winner_robot_two})
        capture = y2p.Capture.create_from_zmq(zmq_message)
        pb_message = dict2pb(pb_server_game.GameState, capture.message)
        assert_equal(pb_message.teams[0].name, looser_team)
        assert_equal(pb_message.teams[1].name, winner_team)
        assert_equal(pb_message.teams[1].players[1], winner_robot_two)


def test_generate():
    y2p.generate()


def main():
    MainTest.test_key_map()

if "__main__" == __name__:
    main()
