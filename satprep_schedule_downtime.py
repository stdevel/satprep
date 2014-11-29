#!/usr/bin/env python

# satprep_schedule_downtime.py - a script for scheduling
# downtimes for hosts monitored by Nagios/Icinga/Thruk/Shinken
#
# 2014 By Christian Stankowic
# <info at stankowic hyphen development dot net>
# https://github.com/stdevel
#

import logging
import sys
from optparse import OptionParser
import requests
from requests.auth import HTTPBasicAuth
import time
from datetime import datetime, timedelta
import csv

#set logger
LOGGER = logging.getLogger('satprep_schedule_downtime')
targetHosts=[]

def setDowntime():
	#set downtime for affected hosts
	for host in targetHosts:
		if options.dryrun == True:
			#simulation
			LOGGER.info("I'd like to schedule downtime for host '" + host + "' for " + options.hours + " hours using the comment '" + options.comment + "'...")
		else:
			#_schedule_ all the downtimes
			LOGGER.debug("Scheduling downtime for host '" + host + "' (hours=" + options.hours + ", comment=" + options.comment + ")...")
			
			#setup headers
			if len(options.userAgent) > 0:
				myHeaders = {'User-Agent': options.userAgent}
			else:
				myHeaders = {'User-Agent': 'satprep Toolkit (https://github.com/stdevel/satprep)'}
			LOGGER.debug("Setting headers: {0}".format(myHeaders))
			
			#setup start and end time for downtime
			current_time=time.strftime("%Y-%m-%d %H:%M:%S")
			end_time=format(datetime.now() + timedelta(hours=int(options.hours)), '%Y-%m-%d %H:%M:%S')
			LOGGER.debug("current_time: {0}".format(current_time))
			LOGGER.debug("end_time: {0}".format(end_time))
			
			#setup payload
			payload = {'cmd_typ': '55', 'cmd_mod': '2', 'host': host, 'com_data': options.comment, 'trigger': '0', 'fixed': '1', 'hours': options.hours, 'minutes': '0', 'start_time': current_time, 'end_time': end_time, 'btnSubmit': 'Commit', 'com_author': options.monUsername, 'childoptions': '0'}
			LOGGER.debug("payload: {0}".format(payload))
			
			#setup HTTP session
			s = requests.Session()
			if options.noAuth == False: s.auth = HTTPBasicAuth(options.monUsername, options.monPassword)
			
			#send POST request
			r = s.post(options.URL+"/cgi-bin/cmd.cgi", data=payload, headers=myHeaders)
			LOGGER.debug("result: {0}".format(r.text))
			
			#check whether request was successful
			if r.status_code != 200:
				LOGGER.error("ERROR: Got HTTP status code " + str(r.status_code) + " instead of 200 while scheduling downtime for host '" + host + "'. Check URL and logon credentials!")
			else:
				if "error" in r.text.lower(): LOGGER.error("ERROR: unable to schedule downtime for host '" + host + "' - please run again with -d / --debug and check HTML output!")
				else: print "Successfully scheduled downtime for host '" + host + "'"



def readFile(file):
	#get affected hosts from CSV report
	global targetHosts
	#read report header and get column index for hostname ,reboot and monitoring flag (if any)
	rFile = open(args[1], 'r')
	header = rFile.readline()
	headers = header.replace("\n","").replace("\r","").split(";")
	repcols = { "hostname" : 666, "errata_reboot" : 666, "system_monitoring" : 666 }
	for name,value in repcols.items():
		try:
			#try to find index
			repcols[name] = headers.index(name)
		except ValueError:
			LOGGER.debug("DEBUG: unable to find column index for " + name + " so I'm disabling it.")
	#print report column indexes
	LOGGER.debug("DEBUG: report column indexes: {0}".format(str(repcols)))
	
	#read report and add affected hosts
	with open(file, 'rb') as csvfile:
		filereader = csv.reader(csvfile, delimiter=';', quotechar='|')
		for row in filereader:
			#print ', '.join(row)
			if options.noIntelligence == True:
				#simply add the damned host
				targetHosts.append(row[repcols["hostname"]])
			else:
				#add host if reboot required and monitoring flag set
				if repcols["system_monitoring"] < 666 and row[repcols["system_monitoring"]] == "1" and repcols["errata_reboot"] < 666 and row[repcols["errata_reboot"]] != "": targetHosts.append(row[repcols["hostname"]])
	#remove duplicates and 'hostname' line
	targetHosts = sorted(set(targetHosts))
	if "hostname" in targetHosts: targetHosts.remove("hostname")
	#print affected hosts
	LOGGER.debug("DEBUG: affected hosts: {0}".format(targetHosts))



def main(options):
	#read file and schedule downtimes
	LOGGER.debug("Options: {0}".format(options))
	LOGGER.debug("Args: {0}".format(args))
	#read file and set downtimes
	readFile(args[1])
	setDowntime()



def parse_options(args=None):
	if args is None:
		args = sys.argv
	
	# define description, version and load parser
	desc = '''%prog is used to schedule downtimes for create the custom information keys used by satprep_snapshot.py to gather more detailed system information. You only need to create those keys once (e.g. before using the first time or after a re-installation of Satellite). Login credentials are assigned using the following shell variables:'''
	parser = OptionParser(description=desc, version="%prog version 0.1")
	#-U / --url
	parser.add_option("-U", "--url", dest="URL", metavar="URL", default="http://localhost/icinga", help="defines the Nagios/Icinga/Thruk/Shinken URL to use (default: http://localhost/icinga)")
	#-u / --username
	parser.add_option("-u", "--username", action="store", dest="monUsername", metavar="USERNAME", help="defines the username used for the monitoring user-interface")
	#-p / --password
	parser.add_option("-p", "--password", action="store", dest="monPassword", metavar="PASSWORD", help="defines the password")
	#-t / --hours
	parser.add_option("-t", "--hours", action="store", dest="hours", default="2", metavar="HOURS", help="sets the time period in hours hosts should be scheduled for downtime (default: 2)")
	#-c / --comment
	parser.add_option("-c", "--comment", action="store", dest="comment", default="System maintenance scheduled by satprep", metavar="COMMENT", help="defines a comment for scheduled downtime (default: 'System maintenance scheduled by satprep')")
	#-x / --no-auth
	parser.add_option("-x", "--no-auth", action="store_true", default=False, dest="noAuth", help="disables HTTP basic auth (often used with Nagios/Icinga and OMD) (default: no)")
	#-a / --user-agent
	parser.add_option("-a", "--user-agent", action="store", default="", metavar="AGENT", dest="userAgent", help="sets a custom HTTP user agent")
	#-d / --debug
	parser.add_option("-d", "--debug", dest="debug", default=False, action="store_true", help="enable debugging outputs")
	#-f / --no-intelligence
	parser.add_option("-f", "--no-intelligence", dest="noIntelligence", action="store_true", default=False, help="disables checking for patches requiring reboot, simply schedules downtime for all hosts mentioned in the CSV report (default: no)")
	#-n / --dry-run
	parser.add_option("-n", "--dry-run", action="store_true", dest="dryrun", default=False, help="only simulates scheduling downtimes")
	
	(options, args) = parser.parse_args(args)
	
	if len(args) != 2:
		print "ERROR: you need to specify exactly one snapshot report!"
		exit(1)
	
	return (options, args)



if __name__ == "__main__":
	(options, args) = parse_options()
	#set logger level
	if options.debug:
		logging.basicConfig(level=logging.DEBUG)
		LOGGER.setLevel(logging.DEBUG)
	else:
		logging.basicConfig()
		LOGGER.setLevel(logging.INFO)
	main(options)
