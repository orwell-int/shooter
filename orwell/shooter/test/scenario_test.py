from nose.tools import assert_equal
from nose.tools import assert_raises
import unittest
import orwell.shooter.scenario as scen
import sys


class ScenarioTest(unittest.TestCase):
    yaml_content = """
messages:
    - hello: !CaptureHello &hello
        destination: TEST1
        message:
            name: "{player_name}"
            address: "{address}"
    - welcome: !CaptureWelcome &welcome
        destination: "{id}"
        message:
            robot: Nono
            team: One
            id: "{id}"
            video_address: "http://fake.com"
            video_port: "{video_port}"
    - ping: !CapturePing &ping
        destination: "{id}"
        message:
            timing: []
    - pong: !CapturePong &pong
        destination: "{id}"
        message:
            timing:
                - logger: "{logger}"
                  timestamp: "{timestamp}"

sockets:
    - !SocketPull &pull_a
        port: 9008
        bind: yes
    - !SocketPull &pull_b
        port: 9009
        bind: yes
    - !SocketPush &push_a
        port: 9008
    - !SocketPush &push_b
        port: 9009

threads:
    - !Thread
        name: "fake server"
        loop: False
        in_socket: *pull_a
        out_socket: *push_b
        flow:
            - !In
                message: *hello
            - !Equal
                values:
                    - "Player"
                    - "{Hello[-1].player_name}"
            - !Equal
                values:
                    - "3.4.5.6"
                    - "{Hello[-1].address}"
            - !Out
                message: *welcome
                arguments:
                    id: '%welcome_id%'
                    video_port: 42
            - !In
                message: *ping
            - !Absent
                values:
                    - "{Ping[-1]}"
                    - "timing"
            - !Out
                message: *pong
                arguments:
                    id: '%welcome_id%'
                    logger: '%logger%'
                    timestamp: %timestamp%
    - !Thread
        name: "fake client"
        loop: False
        in_socket: *pull_b
        out_socket: *push_a
        flow:
            - !Out
                message: *hello
                arguments:
                    player_name: "Player"
                    address: "3.4.5.6"
            - !In
                message: *welcome
            - !Equal
                values:
                    - '%expected_welcome_id%'
                    - "{Welcome[-1].id}"
            - !Equal
                values:
                    - "42"
                    - "{Welcome[-1].video_port}"
            - !Out
                message: *ping
                arguments:
                    id: '%welcome_id%'
            - !In
                message: *pong
            - !Equal
                values:
                    - "%logger%"
                    - "{Pong[-1].logger}"
            - !Equal
                values:
                    - "%timestamp%"
                    - "{Pong[-1].timestamp}"
            - !Equal
                values:
                    - "%timestamp%"
                    - "{Pong[-1].raw.timing[0].timestamp}"
"""

    @staticmethod
    def test_1():
        print("test_1")
        correct_id = "123"
        yaml_content = ScenarioTest.yaml_content.replace(
            "%welcome_id%", correct_id).replace(
                "%expected_welcome_id%", correct_id).replace(
                    "%logger%", "logger").replace(
                        "%timestamp%", "1234")
        with scen.Scenario(yaml_content) as scenario:
            sys.stderr.write("\n" + str(scenario._data) + "\n")
            scenario.build()
            scenario.step_all()

    @staticmethod
    def test_2():
        print("test_2")
        correct_id = "123"
        wrong_id = "666"
        yaml_content = ScenarioTest.yaml_content.replace(
            "%welcome_id%", correct_id).replace(
                "%expected_welcome_id%", wrong_id).replace(
                    "%logger%", "logger").replace(
                        "%timestamp%", "1234")
        thrown = False
        with scen.Scenario(yaml_content) as scenario:
            sys.stderr.write("\n" + str(scenario._data) + "\n")
            scenario.build()
            scenario.step()
            scenario.step()
            scenario.step()
            try:
                # make sure we move to the step receiving the message
                for i in range(50):
                    scenario.step()
                sys.stdout.write("No exception raised.\n")
            except Exception as received_exception:
                expected = ("Failure at index 2 in thread 'fake client'.",)
                thrown = (expected == received_exception.args)
                if not thrown:
                    sys.stdout.write("Exception different from expectation.\n")
                    print("Received:", received_exception)
                else:
                    sys.stdout.write("Exception matched.\n")
        assert(thrown)

    @staticmethod
    def test_3():
        print("test_3")
        correct_id = "123"
        yaml_content = ScenarioTest.yaml_content.replace(
            "%welcome_id%", correct_id).replace(
                "%expected_welcome_id%", correct_id).replace(
                    "%logger%", "logger").replace(
                        "%timestamp%", "1234")
        yaml_content = "\n".join(yaml_content.split("\n")[:-2])
        scenario = scen.Scenario(yaml_content)
        try:
            scenario.build()
            thrown = False
        except Exception as expected_exception:
            thrown = (
                ("Only {} value(s) found but 2 expected.".format(1),)
                == expected_exception.args)
            print(expected_exception)
        assert(thrown)


class FakeMessage(object):
    def __init__(self, message_type, captured, destination, raw=None):
        self.message_type = message_type
        self.captured = captured
        self.destination = destination
        self.raw = raw


class CaptureRepositoryTest(unittest.TestCase):
    @staticmethod
    def _check(repo, pattern, expected):
        is_exception = isinstance(expected, BaseException)
        if is_exception:
            exception_type = type(expected)
            try:
                repo.expand(pattern)
            except exception_type as exception:
                assert_equal(repr(expected), repr(exception), pattern)
        else:
            expanded = repo.expand(pattern)
            assert_equal(expected, expanded, pattern)

    @staticmethod
    def test_1():
        print("test_1")
        name = "NONO"
        identifier = "ID42"
        repo = scen.CaptureRepository()
        repo.add_received_message(
                FakeMessage("Register", [{"name": name}], "dest"))
        CaptureRepositoryTest._check(repo, "{Register[-1].name}", name)
        CaptureRepositoryTest._check(repo, "{Register[0].name}", name)
        repo.add_received_message(
            FakeMessage("Register", [{"identifier": identifier}], "dest"))
        CaptureRepositoryTest._check(
            repo, "{Register[-1].name}",
            AttributeError(
                "'CaptureConverter' object has no attribute 'name'"))
        CaptureRepositoryTest._check(
            repo, "{Register[-1].identifier}", identifier)
        CaptureRepositoryTest._check(
            repo, "{Register[0].name}", name)


def main():
    # ScenarioTest.test_1()
    ScenarioTest.test_2()
    # ScenarioTest.test_3()
    # CaptureRepositoryTest.test_1()

if "__main__" == __name__:
    main()
