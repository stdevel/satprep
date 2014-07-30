#!/usr/bin/python

# satprep_install_custominfos.py - a script for creating
# custom information that can be automatically inserted in
# patch reports.
#
# 2014 By Christian Stankowic
# <info at stankowic hyphen development dot net>
# https://github.com/stdevel
#

from optparse import OptionParser
import xmlrpclib
import stat
import os
import getpass
import pprint

# TODO: state prod/test


# list of supported API levels
supportedAPI = ["11.1", "12", "13", "13.0", "14", "14.0", "15", "15.0"]

if __name__ == "__main__":
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

	(options, args) = parser.parse_args()

	if options.debug:
		print "DEBUG: " + str(options) + str(args)

	# define custom keys which are going to be created
	customKeys = {"SYSTEM_OWNER": "Defines the system's owner - this is needed for creating automated maintenance reports", "SYSTEM_MONITORING": "Defines whether the system is monitored",
				  "SYSTEM_MONITORING_NOTES": "Defines additional notes to the system's monitoring state (e.g. test system)", "SYSTEM_CLUSTER": "Defines whether the system is part of a cluster",
				  "SYSTEM_BACKUP_NOTES": "Defines additional notes to the system's backup state (e.g. test system)", "SYSTEM_BACKUP": "Defines whether the system is backed up",
				  "SYSTEM_ANTIVIR_NOTES": "Defines additional notes to the anti-virus state of a system (e.g. anti-virus is implemented using XYZ)",
				  "SYSTEM_ANTIVIR": "Defines whether the system is protected with anti-virus software",
				  "SYSTEM_PROD": "Defines whehter the system is a production host"}

	# define URL and login information
	SATELLITE_URL = "http://" + options.server + "/rpc/api"

	if options.dryrun:
		print "I'd like to create the following system information keys:\n"
		pprint.pprint(customKeys)
		exit(0)

	# setup client and key depending on mode
	client = xmlrpclib.Server(SATELLITE_URL, verbose=options.debug)
	if options.authfile:
		if options.debug:
			print "DEBUG: using authfile"
		try:
			# check filemode and read file
			filemode = oct(stat.S_IMODE(os.lstat(options.authfile).st_mode))
			if filemode == "0600":
				if options.debug:
					print "DEBUG: file permission (" + filemode + ") matches 0600"
				with open(options.authfile, "r") as fo:
					s_username = fo.readline()
					s_password = fo.readline()
				key = client.auth.login(s_username, s_password)
			else:
				if options.verbose:
					print "ERROR: file permission (" + filemode + ") not matching 0600!"
				exit(1)
		except OSError:
			print "ERROR: file non-existent or permissions not 0600!"
			exit(1)
	elif "SATELLITE_LOGIN" in os.environ and "SATELLITE_PASSWORD" in os.environ:
		# shell variables
		if options.debug:
			print "DEBUG: checking shell variables"
		key = client.auth.login(
			os.environ["SATELLITE_LOGIN"], os.environ["SATELLITE_PASSWORD"])
	else:
		# prompt user
		if options.debug:
			print "DEBUG: prompting for login credentials"
		s_username = raw_input("Username: ")
		s_password = getpass.getpass("Password: ")
		key = client.auth.login(s_username, s_password)

	# check whether the API version matches the minimum required
	api_level = client.api.getVersion()
	if not api_level in supportedAPI:
		print "ERROR: your API version (" + api_level + ") does not support the required calls. You'll need API version 1.8 (11.1) or higher!"
		exit(1)
	else:
		if options.debug:
			print "INFO: supported API version (" + api_level + ") found."

	# create keys
	# get also pre-defined keys
	definedKeys = client.system.custominfo.listAllKeys(key)
	resultcode = 0
	if options.debug:
		print "DEBUG: pre-defined custom information keys:\n" + str(definedKeys)
	for newKey in customKeys:
		if options.debug:
			print "DEBUG: about to add system information key '" + newKey + "' with description '" + customKeys.get(newKey) + "'..."
		if newKey in str(definedKeys):
			if options.force == True:
				if options.verbose:
					print "INFO: overwriting pre-existing key '" + newKey + "' with description '" + customKeys.get(newKey) + "'..."
				resultcode = client.system.custominfo.updateKey(
					key, newKey, customKeys.get(newKey))
			else:
				print "ERROR: key '" + newKey + "' already exists. Use -f / --force to overwrite!"
		else:
			resultcode = client.system.custominfo.createKey(
				key, newKey, customKeys.get(newKey))
		if resultcode == 1:
			if options.verbose:
				print "INFO: successfully created/updated information key '" + newKey + "'"
		else:
			if newKey not in customKeys:
				print "ERROR: unable to create key '" + newKey + "': check your account permissions!"
