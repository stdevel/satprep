#!/usr/bin/env python
# -*- coding: utf-8 -*-

import getpass
import logging
import os
import stat
import sys
import requests
from requests.auth import HTTPBasicAuth
import time
from datetime import datetime, timedelta

LOGGER =  logging.getLogger('satprep-shared')

SUPPORTED_API_LEVELS = ["11.1", "12", "13", "13.0", "14", "14.0", "15", "15.0"]


class APILevelNotSupportedException(Exception):
    pass


def check_if_api_is_supported(client):
#check whether API is supported
    api_level = client.api.getVersion()
    if api_level not in SUPPORTED_API_LEVELS:
        raise APILevelNotSupportedException(
            "Your API version ({0}) does not support the required calls. "
            "You'll need API version 1.8 (11.1) or higher!".format(api_level)
        )
    else:
        LOGGER.info("INFO: supported API version (" + api_level + ") found.")

def get_credentials(input_file=None):
#retrieve credentials
    if input_file:
        LOGGER.debug("DEBUG: using authfile")
        try:
            # check filemode and read file
            filemode = oct(stat.S_IMODE(os.lstat(input_file).st_mode))
            if filemode == "0600":
                LOGGER.debug("DEBUG: file permission matches 0600")
                with open(input_file, "r") as auth_file:
                    s_username = auth_file.readline().replace("\n", "")
                    s_password = auth_file.readline().replace("\n", "")
                return (s_username, s_password)
            else:
                LOGGER.warning("INFO: file permission (" + filemode + ") not matching 0600!")
                sys.exit(1)
        except OSError:
            LOGGER.warning("INFO: file non-existent or permissions not 0600!")
            sys.exit(1)
    elif "SATELLITE_LOGIN" in os.environ and "SATELLITE_PASSWORD" in os.environ:
        # shell variables
        LOGGER.debug("DEBUG: checking shell variables")
        return (os.environ["SATELLITE_LOGIN"], os.environ["SATELLITE_PASSWORD"])
    else:
        # prompt user
        LOGGER.debug("DEBUG: prompting for login credentials")
        s_username = raw_input("Username: ")
        s_password = getpass.getpass("Password: ")
        return (s_username, s_password)

def schedule_downtime(url, monUsername, monPassword, host, hours, comment, agent="", noAuth=False, unschedule=False):
#schedule downtime
	#setup headers
	if len(agent) > 0:
		myHeaders = {'User-Agent': agent}
	else:
		myHeaders = {'User-Agent': 'satprep Toolkit (https://github.com/stdevel/satprep)'}
	LOGGER.debug("Setting headers: {0}".format(myHeaders))
	
	#setup start and end time for downtime
	current_time=time.strftime("%Y-%m-%d %H:%M:%S")
	end_time=format(datetime.now() + timedelta(hours=int(hours)), '%Y-%m-%d %H:%M:%S')
	LOGGER.debug("current_time: {0}".format(current_time))
	LOGGER.debug("end_time: {0}".format(end_time))
	
	#setup payload
	if unschedule:
		payload = {'cmd_typ': '171', 'cmd_mod': '2', 'host': host, 'btnSubmit': 'Commit'}
	else:
		payload = {'cmd_typ': '55', 'cmd_mod': '2', 'host': host, 'com_data': comment, 'trigger': '0', 'fixed': '1', 'hours': hours, 'minutes': '0', 'start_time': current_time, 'end_time': end_time, 'btnSubmit': 'Commit', 'com_author': monUsername, 'childoptions': '0'}
	LOGGER.debug("payload: {0}".format(payload))
	
	#setup HTTP session
	s = requests.Session()
	if noAuth == False: s.auth = HTTPBasicAuth(monUsername, monPassword)
	
	#send POST request
	r = s.post(url+"/cgi-bin/cmd.cgi", data=payload, headers=myHeaders)
	try:
		LOGGER.debug("result: {0}".format(r.text))
	except:
		LOGGER.debug("result: none - check URL/authentification method!")
	
	#check whether request was successful
	if r.status_code != 200:
		LOGGER.error("ERROR: Got HTTP status code " + str(r.status_code) + " instead of 200 while scheduling downtime for host '" + host + "'. Check URL and logon credentials!")
		return False
	else:
		if "error" in r.text.lower(): LOGGER.error("ERROR: unable to (un)schedule downtime for host '" + host + "' - please run again with -d / --debug and check HTML output! (does this host exist?!)")
		else: print "Successfully (un)scheduled downtime for host '" + host + "'"
		return True
