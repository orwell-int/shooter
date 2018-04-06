import logging
import sys
import argparse
import time

import orwell.shooter.scenario as scen


def main(argv=sys.argv[1:]):
    parser = argparse.ArgumentParser(description='Scenario shooter.')
    parser.add_argument('scenario_file', help='YAML scenario file.')
    parser.add_argument(
        '--delay', '-d',
        help='Delay between steps.',
        default=0,
        action="store",
        metavar="DELAY",
        type=int)
    parser.add_argument(
        '--verbose', '-v',
        help='Verbose mode',
        default=False,
        action="store_true")
    arguments = parser.parse_args()
    log = logging.getLogger(__name__)
    handler = logging.StreamHandler()
    log.addHandler(handler)
    if (arguments.verbose):
        log.setLevel(logging.DEBUG)
    else:
        log.setLevel(logging.INFO)
    scen.configure_logging(arguments.verbose)
    scenario_file = arguments.scenario_file
    delay = arguments.delay
    log.debug('Open file "{}" as YAML scenario.'.format(scenario_file))
    log.debug('Time to wait between steps (-d): {}'.format(delay))
    with open(scenario_file, 'r') as yaml_scenario:
        yaml_content = yaml_scenario.read()
        with scen.Scenario(yaml_content) as scenario:
            scenario.build()
            while scenario.has_more_steps:
                log.debug("step")
                scenario.step()
                time.sleep(delay)


if ("__main__" == __name__):
    sys.exit(main(sys.argv[1:]))  # pragma: no coverage
