#!/usr/bin/python

# satprep_install_custominfos.py - a script for creating
# custom information that can be automatically inserted in
# patch reports.
#
# 2014 By Christian Stankowic
# <info at stankowic hyphen development dot net>
# https://github.com/stdevel
#

import logging
import pprint
import sys
import xmlrpclib
from optparse import OptionParser
from satprep_shared import SUPPORTED_API_LEVELS, get_credentials
# TODO: state prod/test

CUSTOM_KEYS = {
	"SYSTEM_OWNER": "Defines the system's owner - this is needed for creating automated maintenance reports",
	"SYSTEM_MONITORING": "Defines whether the system is monitored",
	"SYSTEM_MONITORING_NOTES": "Defines additional notes to the system's monitoring state (e.g. test system)",
	"SYSTEM_CLUSTER": "Defines whether the system is part of a cluster",
	"SYSTEM_BACKUP_NOTES": "Defines additional notes to the system's backup state (e.g. test system)",
	"SYSTEM_BACKUP": "Defines whether the system is backed up",
	"SYSTEM_ANTIVIR_NOTES": "Defines additional notes to the anti-virus state of a system (e.g. anti-virus is implemented using XYZ)",
	"SYSTEM_ANTIVIR": "Defines whether the system is protected with anti-virus software",
	"SYSTEM_PROD": "Defines whehter the system is a production host"
}

LOGGER = logging.getLogger('satprep')

def main(options):
	LOGGER.debug("Options: {0}".format(options))
	LOGGER.debug("Args: {0}".format(args))

	if options.dryrun:
		LOGGER.info("I'd like to create the following system information keys:\n{0}".format(pprint.pformat(CUSTOM_KEYS)))
		sys.exit(0)

	(username, password) = get_credentials(options.authfile)

	satellite_url = "http://{0}/rpc/api".format(options.server)
	client = xmlrpclib.Server(satellite_url, verbose=options.debug)
	key = client.auth.login(username, password)

	check_if_api_is_supported(client)
	create_custom_keys(client, key, force_creation=options.force)


def check_if_api_is_supported(client):
	api_level = client.api.getVersion()
	if api_level not in SUPPORTED_API_LEVELS:
		LOGGER.warning("INFO: your API version (" + api_level + ") does not support the required calls. You'll need API version 1.8 (11.1) or higher!")
		sys.exit(1)
	else:
		LOGGER.info("INFO: supported API version (" + api_level + ") found.")


def create_custom_keys(client, session_key, force_creation=False):
	definedKeys = client.system.custominfo.listAllKeys(session_key)
	defined_keys_as_str = str(definedKeys)

	LOGGER.debug("DEBUG: pre-defined custom information keys: {0}".format(definedKeys))
	for new_key in CUSTOM_KEYS:
		resultcode = 0

		LOGGER.debug("DEBUG: about to add system information key '" + new_key + "' with description '" + CUSTOM_KEYS.get(new_key) + "'...")
		if new_key in defined_keys_as_str:
			if force_creation:
				LOGGER.info("INFO: overwriting pre-existing key '" + new_key + "' with description '" + CUSTOM_KEYS.get(new_key) + "'...")

				resultcode = client.system.custominfo.updateKey(
					session_key, new_key, CUSTOM_KEYS.get(new_key))
			else:
				LOGGER.warning("INFO: key '" + new_key + "' already exists. Use -f / --force to overwrite!")
		else:
			resultcode = client.system.custominfo.createKey(
				session_key, new_key, CUSTOM_KEYS.get(new_key))

		if resultcode == 1:
			LOGGER.info("INFO: successfully created/updated information key '{0}'".format(new_key))
		else:
			if new_key not in CUSTOM_KEYS:
				LOGGER.warning("INFO: unable to create key '{0}': check your account permissions!".format(new_key))


def parse_options(args=None):
	if args is None:
		args = sys.argv

	# define description, version and load parser
	desc = '''%prog is used to create the custom information keys used by satprep_snapshot.py to gather more detailed system information. You only need to create those keys once (e.g. before using the first time or after a re-installation of Satellite). Login credentials are assigned using the following shell variables:

	SATELLITE_LOGIN  username
	SATELLITE_PASSWORD  password

	It is also possible to create an authfile (permissions 0600) for usage with this script. The first line needs to contain the username, the second line should consist of the appropriate password.
If you're not defining variables or an authfile you will be prompted to enter your login information.

	Checkout the GitHub page for updates: https://github.com/stdevel/satprep'''
	parser = OptionParser(description=desc, version="%prog version 0.1")
	parser.add_option("-a", "--authfile", dest="authfile", metavar="FILE",
					  default="", help="defines an auth file to use instead of shell variables")
	parser.add_option("-s", "--server", dest="server", metavar="SERVER",
					  default="localhost", help="defines the server to use")
	parser.add_option("-q", "--quiet", action="store_false", dest="verbose",
					  default=True, help="don't print status messages to stdout")
	parser.add_option("-d", "--debug", dest="debug", default=False,
					  action="store_true", help="enable debugging outputs")
	parser.add_option("-n", "--dry-run", action="store_true", dest="dryrun",
					  default=False, help="only simulates the creation of custom keys")
	parser.add_option("-f", "--force", action="store_true", dest="force",
					  default=False, help="overwrites previously created custom keys with the same name")

	(options, args) = parser.parse_args(args)

	return (options, args)


if __name__ == "__main__":
	(options, args) = parse_options()

	if options.debug:
		logging.basicConfig(level=logging.DEBUG)
		LOGGER.setLevel(logging.DEBUG)
	else:
		LOGGER.setLevel(logging.WARNING)

	main(options)
