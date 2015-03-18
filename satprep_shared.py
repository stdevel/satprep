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
import libvirt



#some global variables
LIBVIRT_USERNAME=""
LIBVIRT_PASSWORD=""

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
        LOGGER.info("Supported API version (" + api_level + ") found.")



def get_credentials(type, input_file=None):
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
                LOGGER.warning("File permission (" + filemode + ") not matching 0600!")
                #sys.exit(1)
        except OSError:
		LOGGER.warning("File non-existent or permissions not 0600!")
		#sys.exit(1)
        	LOGGER.debug("DEBUG: prompting for login credentials as we have a faulty file")
		s_username = raw_input(type + " Username: ")
		s_password = getpass.getpass(type + " Password: ")
		return (s_username, s_password)
    elif type.upper()+"_LOGIN" in os.environ and type.upper()+"_PASSWORD" in os.environ:
	# shell variables
	LOGGER.debug("DEBUG: checking shell variables")
	return (os.environ[type.upper()+"_LOGIN"], os.environ[type.upper()+"_PASSWORD"])
    else:
	# prompt user
	LOGGER.debug("DEBUG: prompting for login credentials")
	s_username = raw_input(type + " Username: ")
	s_password = getpass.getpass(type + " Password: ")
	return (s_username, s_password)



def has_snapshot(virtURI, hostUsername, hostPassword, vmName, name):
#check whether VM has a snapshot
	#authentificate
	global LIBVIRT_USERNAME
	global LIBVIRT_PASSWORD
	LIBVIRT_USERNAME = hostUsername
	LIBVIRT_PASSWORD = hostPassword
	
	LOGGER.debug("Checking for snapshots with user '" + hostUsername + "'...")
	auth = [[libvirt.VIR_CRED_AUTHNAME, libvirt.VIR_CRED_PASSPHRASE], get_libvirt_credentials, None]
	
	conn = libvirt.openAuth(virtURI, auth, 0)
	
	if conn == None:
		LOGGER.error("Unable to establish connection to hypervisor!")
		return False
	try:
		targetVM = conn.lookupByName(vmName)
		mySnaps = targetVM.snapshotListNames(0)
		if name in mySnaps: return True
	except Exception,e: 
		return False



def is_downtime(url, monUsername, monPassword, host, agent, noAuth=False):
#check whether host is scheduled for downtime
	#setup headers
	if len(agent) > 0: myHeaders = {'User-Agent': agent}
	else: myHeaders = {'User-Agent': 'satprep Toolkit (https://github.com/stdevel/satprep)'}
	LOGGER.debug("Setting headers: {0}".format(myHeaders))
	
	#setup HTTP session
	s = requests.Session()
	if noAuth == False: s.auth = HTTPBasicAuth(monUsername, monPassword)
	
	#send GET request
	r = s.get(url+"/cgi-bin/status.cgi?host=all&hostprops=1&style=hostdetail", headers=myHeaders)
	try:
		LOGGER.debug("result: {0}".format(r.text))
	except:
		LOGGER.debug("result: none - check URL/authentification method!")
	
	#check whether request was successful
	if r.status_code != 200:
		LOGGER.error("Got HTTP status code " + str(r.status_code) + " instead of 200 while checking downtime for host '" + host + "'. Check URL and logon credentials!")
		return False
	else:
		if "error" in r.text.lower(): LOGGER.error("Unable to get downtime for host '" + host + "' - please run again with -d / --debug and check HTML output! (does this host exist?!)")
		else:
			if host.lower() not in r.text.lower():
				LOGGER.info("Host '" + host + "' currently NOT scheduled for downtime.")
				return False
			else:
				LOGGER.info("Host '" + host + "' currently in scheduled downtime.")
				return True



def schedule_downtime(url, monUsername, monPassword, host, hours, comment, agent="", noAuth=False, unschedule=False):
#(un)schedule downtime
	#setup headers
	if len(agent) > 0: myHeaders = {'User-Agent': agent}
	else: myHeaders = {'User-Agent': 'satprep Toolkit (https://github.com/stdevel/satprep)'}
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
		LOGGER.error("Got HTTP status code " + str(r.status_code) + " instead of 200 while scheduling downtime for host '" + host + "'. Check URL and logon credentials!")
		return False
	else:
		if "error" in r.text.lower(): LOGGER.error("Unable to (un)schedule downtime for host '" + host + "' - please run again with -d / --debug and check HTML output! (does this host exist?!)")
		else:
			if unschedule: print "Successfully unscheduled downtime for host '" + host + "'"
			else: print "Successfully scheduled downtime for host '" + host + "'"
		return True



def get_libvirt_credentials(credentials, user_data):
#get credentials for libvirt
	global LIBVIRT_USERNAME
	global LIBVIRT_PASSWORD
	
	for credential in credentials:
		if credential[0] == libvirt.VIR_CRED_AUTHNAME:
			# prompt the user to input a authname. display the provided message
			#credential[4] = raw_input(credential[1] + ": ")
			credential[4] = LIBVIRT_USERNAME
			
			# if the user just hits enter raw_input() returns an empty string.
			# in this case return the default result through the last item of
			# the list
			if len(credential[4]) == 0:
				credential[4] = credential[3]
		elif credential[0] == libvirt.VIR_CRED_PASSPHRASE:
			# use the getpass module to prompt the user to input a password.
			# display the provided message and return the result through the
			# last item of the list
			#credential[4] = getpass.getpass(credential[1] + ": ")
			credential[4] = LIBVIRT_PASSWORD
		else:
			return -1
	return 0



#def create_snapshot(virtURI, virtUsername, virtPassword, hostUsername, hostPassword, vmName, name, comment, remove=False):
def create_snapshot(virtURI, hostUsername, hostPassword, vmName, name, comment, remove=False):
#create/remove snapshot
	#authentificate
	global LIBVIRT_USERNAME
	global LIBVIRT_PASSWORD
	LIBVIRT_USERNAME = hostUsername
	LIBVIRT_PASSWORD = hostPassword

	LOGGER.debug("Creating snapshot with user '" + hostUsername + "'...")
	auth = [[libvirt.VIR_CRED_AUTHNAME, libvirt.VIR_CRED_PASSPHRASE], get_libvirt_credentials, None]
	
	conn = libvirt.openAuth(virtURI, auth, 0)
	
	if conn == None:
		LOGGER.error("Unable to establish connection to hypervisor!")
		#sys.exit(1)
		return False
	
	try:
		targetVM = conn.lookupByName(vmName)
		if remove:
			#remove snapshot
			targetSnap = targetVM.snapshotLookupByName(name, 0)
			return targetSnap.delete(0)
		else:
			#create snapshot
			snapXML = "<domainsnapshot><name>" + name + "</name><description>" + comment + "</description></domainsnapshot>"
			return targetVM.snapshotCreateXML(snapXML, 0)
	except Exception,e: 
		#Snapshot 'Before maintenance' already exists
		if remove:
			LOGGER.error("Unable to remove snapshot: '" + str(e) + "'")
		else:
			LOGGER.error("Unable to create snapshot: '" + str(e) + "'")
		return False
