#!/usr/bin/env python
# -*- coding: utf-8 -*-

# satprep_install_custominfos.py - a script for creating
# custom information that can be automatically inserted in
# patch reports.
#
# 2015 By Christian Stankowic
# <info at stankowic hyphen development dot net>
# https://github.com/stdevel
#

import logging
import pprint
import sys
import xmlrpclib
from optparse import OptionParser, OptionGroup
from satprep_shared import check_if_api_is_supported, get_credentials



#key definitions
CUSTOM_KEYS = {
        "SYSTEM_OWNER": "Defines the system's owner - this is needed for creating automated maintenance reports",
        "SYSTEM_MONITORING": "Defines whether the system is monitored",
        "SYSTEM_MONITORING_NOTES": "Defines additional notes to the system's monitoring state (e.g. test system)",
        "SYSTEM_CLUSTER": "Defines whether the system is part of a cluster",
        "SYSTEM_BACKUP_NOTES": "Defines additional notes to the system's backup state (e.g. test system)",
        "SYSTEM_BACKUP": "Defines whether the system is backed up",
        "SYSTEM_ANTIVIR_NOTES": "Defines additional notes to the anti-virus state of a system (e.g. anti-virus is implemented using XYZ)",
        "SYSTEM_ANTIVIR": "Defines whether the system is protected with anti-virus software",
        "SYSTEM_PROD": "Defines whehter the system is a production host",
	"SYSTEM_MONITORING_HOST": "Alternate monitoring server URL",
	"SYSTEM_MONITORING_HOST_AUTH": "Authentification location for alternate monitoring server",
	"SYSTEM_MONITORING_NAME": "Defines an alternative monitoring hostname",
	"SYSTEM_VIRT_HOST": "Alternate virtual host (e.g. ESXi, vCenter) - use libvirt URI",
	"SYSTEM_VIRT_HOST_AUTH": "Authentification location for alternate virtual host",
	"SYSTEM_VIRT_SNAPSHOT": "Defines whether the system should be protected by a snapshot",
	"SYSTEM_VIRT_VMNAME": "Defines an alternative VM object name"
}
#define logger
LOGGER = logging.getLogger('satprep_install_custominfos')



def main(options):
        LOGGER.debug("Options: {0}".format(options))
        LOGGER.debug("Args: {0}".format(args))

        if options.dryrun:
		if options.uninstall: LOGGER.info("I'd like to uninstall the following system information keys:\n{0}".format(pprint.pformat(CUSTOM_KEYS)))
		else: LOGGER.info("I'd like to create the following system information keys:\n{0}".format(pprint.pformat(CUSTOM_KEYS)))
                sys.exit(0)

        (username, password) = get_credentials("Satellite", options.authfile)

        satellite_url = "http://{0}/rpc/api".format(options.server)
        client = xmlrpclib.Server(satellite_url, verbose=options.debug)
        key = client.auth.login(username, password)

        check_if_api_is_supported(client)

        #create or remove keys
        if options.uninstall:
                LOGGER.info("I'm going to remove previously created system information keys used by satprep")
                remove_custom_keys(client, key)
        else:
                create_custom_keys(client, key, force_creation=options.force)



def create_custom_keys(client, session_key, force_creation=False):
        definedKeys = client.system.custominfo.listAllKeys(session_key)
        defined_keys_as_str = str(definedKeys)

        LOGGER.debug("DEBUG: pre-defined custom information keys: {0}".format(definedKeys))
        for new_key in CUSTOM_KEYS:
                resultcode = 0

                LOGGER.debug("DEBUG: about to add system information key '" + new_key + "' with description '" + CUSTOM_KEYS.get(new_key) + "'...")
                if new_key in defined_keys_as_str:
                        if force_creation:
                                LOGGER.info("Overwriting pre-existing key '" + new_key + "' with description '" + CUSTOM_KEYS.get(new_key) + "'...")

                                resultcode = client.system.custominfo.updateKey(
                                        session_key, new_key, CUSTOM_KEYS.get(new_key))
                        else:
                                LOGGER.warning("Key '" + new_key + "' already exists. Use -f / --force to overwrite!")
                else:
                        resultcode = client.system.custominfo.createKey(
                                session_key, new_key, CUSTOM_KEYS.get(new_key))

                if resultcode == 1:
                        LOGGER.info("Successfully created/updated information key '{0}'".format(new_key))
                else:
                        if new_key not in CUSTOM_KEYS:
                                LOGGER.warning("Unable to create key '{0}': check your account permissions!".format(new_key))


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
        parser = OptionParser(description=desc, version="%prog version 0.3")
	#define option groups
	genOpts = OptionGroup(parser, "Generic Options")
	srvOpts = OptionGroup(parser, "Server Options")
	parser.add_option_group(genOpts)
	parser.add_option_group(srvOpts)
	
	#GENERIC OPTIONS
	#-q / --quiet
	genOpts.add_option("-q", "--quiet", action="store_false", dest="verbose", default=True, help="don't print status messages to stdout (default: no)")
	#-d / --debug
	genOpts.add_option("-d", "--debug", dest="debug", default=False, action="store_true", help="enable debugging outputs (default: no)")
	
	#SERVER OPTIONS
	#-a / --authfile
	srvOpts.add_option("-a", "--authfile", dest="authfile", metavar="FILE", default="", help="defines an auth file to use instead of shell variables")
	#-s / --server
	srvOpts.add_option("-s", "--server", dest="server", metavar="SERVER", default="localhost", help="defines the server to use")
	#-n / --dry-run
	srvOpts.add_option("-n", "--dry-run", action="store_true", dest="dryrun", default=False, help="only simulates the creation of custom keys (default: no)")
	#-f / --force
	srvOpts.add_option("-f", "--force", action="store_true", dest="force", default=False, help="overwrites previously created custom keys with the same name (default: no)")
	#-u / --uninstall
	srvOpts.add_option("-u", "--uninstall", action="store_true", dest="uninstall", default=False, help="removes previously installed custom info keys (default: no)")

        (options, args) = parser.parse_args(args)

        return (options, args)



def remove_custom_keys(client, session_key):

        for key in CUSTOM_KEYS:
                resultcode = 0
                LOGGER.debug("DEBUG: about to add system information key '" + key + "'...")
                resultcode = client.system.custominfo.deleteKey(session_key, key)

                if resultcode == 1:
                        LOGGER.info("Successfully removed information key '{0}'".format(key))
                else:
                        LOGGER.warning("Unable to remove key '{0}': check your account permissions!".format(key))



if __name__ == "__main__":
        (options, args) = parse_options()

        if options.debug:
                logging.basicConfig(level=logging.DEBUG)
                LOGGER.setLevel(logging.DEBUG)
        else:
                logging.basicConfig()
                LOGGER.setLevel(logging.INFO)

        main(options)
