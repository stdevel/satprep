#!/usr/bin/env python
# -*- coding: utf-8 -*-

# satprep_patch_freeze.py - a script for freezing patches
# and errata for managed systems.
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
from satprep_shared import check_if_api_is_supported, get_credentials, is_blacklisted
import datetime



#define globale variables
LOGGER = logging.getLogger('satprep_patch_freeze')
mySystems=[]
myChannels={}



def getChannels(client, key):
	#get _all_ the hosts
	satGroups=[]
	global myChannels
	global mySystems
	
	for item in client.systemgroup.listAllGroups(key):
		satGroups.append(item["name"])
	LOGGER.debug("This Satellite server's groups: '{0}'".format(satGroups))
	tempHosts=[]
	for host in options.targetSystems:
		if len(client.system.getId(key, host)) != 0: tempHosts.append(host)
		else: LOGGER.error("System '{0}' appears not to be a valid host".format(host))
	for group in options.targetGroups:
		if group in satGroups:
			groupHosts = client.systemgroup.listSystems(key, group)
			for host in groupHosts:
				tempHosts.append(host["profile_name"])
				LOGGER.debug("Adding system '{0}'".format(host["profile_name"]))
		else: LOGGER.error("Group '{0}' appears not to be a valid group".format(group))
	#removing blacklisted or hosts without base channel
	for host in tempHosts:
		hostId = client.system.getId(key, host)
		if is_blacklisted(host, options.exclude):
			LOGGER.debug("System '{0}' is blacklisted".format(host))
		elif len(client.system.getSubscribedBaseChannel(key, hostId[0]["id"])) < 1:
			LOGGER.error("System '{0}' has no base channel".format(host))
		else:
			LOGGER.debug("Adding valid system '{0}'".format(host))	
			mySystems.append(host)
	#list hosts or die in a fire
	if len(mySystems) == 0:
		LOGGER.info("Nothing to do, giving up!")
		sys.exit(1)
	LOGGER.debug("Validated hosts:")
	for host in mySystems: LOGGER.debug(host)
	
	#get _all_ the software channels
	for host in mySystems:
		#adding base-channel
		LOGGER.debug("Check base-channel for system '{0}'".format(host))
		hostId = client.system.getId(key, host)
		try:
			LOGGER.debug("This system's profile ID: {0}".format(hostId))
			baseChannel = client.system.getSubscribedBaseChannel(key, hostId[0]["id"])
			cleanBase = baseChannel["label"]
			if "." in cleanBase: cleanBase = cleanBase[cleanBase.find(".")+1:]
			if cleanBase not in myChannels:
				#channel non-present
				LOGGER.debug("Adding channel '{0}'".format(cleanBase))
				myChannels[cleanBase]=[]
				#adding child channels
				childChannels = client.system.listSubscribedChildChannels(key, hostId[0]["id"])
				for channel in childChannels:
					cleanChild = channel["label"]
					if "." in cleanChild: cleanChild = cleanChild[cleanChild.find(".")+1:]
					if cleanChild not in myChannels[cleanBase]:
						LOGGER.debug("Adding child-channel '{0}'".format(cleanChild))
						myChannels[cleanBase].append(cleanChild)
				#also list non-subscribed channels if wanted
				if options.allSubchannels:
					childChannels = client.system.listSubscribableChildChannels(key, hostId[0]["id"])
					for channel in childChannels:
						if cleanChild not in myChannels[cleanBase]:
							LOGGER.debug("Adding non-subscribed child-channel '{0}'".format(cleanChild))
							myChannels[cleanBase].append(cleanChild)
		except:
			LOGGER.error("Unable to scan system '{0}', check hostname, profile name and whether a base channel was set!".format(host))
	#print channel information
	LOGGER.debug("Software channel tree: {0}".format(str(myChannels)))



def cloneChannels(client, key, date, label, unfreeze=False):
	if unfreeze:
		#remove clones
		for channel in myChannels:
			#remove child-channels
			for child in myChannels[channel]:
				if options.dryrun: LOGGER.info("I'd like to remove cloned child-channel '{0}'".format(options.targetLabel+"-"+options.targetDate+"."+child))
				else:
					try:
						LOGGER.info("Deleting child-channel '{0}'".format(options.targetLabel+"-"+options.targetDate+"."+child))
						result = client.channel.software.delete(key, options.targetLabel+"-"+options.targetDate+"."+child)
					except xmlrpclib.Fault as e:
						LOGGER.error("Unable to remove child-channel '{0}': '{1}'".format(options.targetLabel+"-"+options.targetDate+"."+child, e.faultString))
					except xmlrpclib.ProtocolError as e:
						LOGGER.error("Unable to remove child-channel '{0}': '{1}'".format(options.targetLabel+"-"+options.targetDate+"."+child, e.errmsg))
					except:
						LOGGER.error("Unable to remove child-channel '{0}'!".format(options.targetLabel+"-"+options.targetDate+"."+child))
		#remove base-channel
		if options.dryrun: LOGGER.info("I'd like to remove cloned base-channel '{0}'".format(options.targetLabel+"-"+options.targetDate+"."+channel))
		else:
			try:
				LOGGER.info("Deleting base-channel '{0}'".format(options.targetLabel+"-"+options.targetDate+"."+channel))
				result = client.channel.software.delete(key, options.targetLabel+"-"+options.targetDate+"."+channel)
			except: LOGGER.error("Unable to remove base-channel '{0}'!".format(channel))
		return True
	
	#clone channels
	for channel in myChannels:
		#clone base-channels
		myargs={"name" : "Cloned " + channel + " from "+options.targetDate+" ("+options.targetLabel+")", "label" : options.targetLabel+"-"+options.targetDate+"."+channel, "summary" : "Software channel cloned by Satprep"}
		if options.dryrun:
			LOGGER.info("I'd like to clone base-channel '{0}' as '{1}'".format(channel, options.targetLabel+"-"+options.targetDate+"."+channel))
		else:
			LOGGER.info("Cloning base-channel '{0}' as '{1}'".format(channel, options.targetLabel+"-"+options.targetDate+"."+channel))
			try:
				result = client.channel.software.clone(key, channel, myargs, False)
				if result != 0: LOGGER.debug("Cloned base-channel")
			except xmlrpclib.Fault as e:
				LOGGER.error("Unable to clone base-channel: " + e.faultString)
			except xmlrpclib.ProtocolError as e:
				LOGGER.error("Unable to clone base-channel: " + e.errmsg)
			except:
				LOGGER.error("Unable to clone base-channel: " + str(sys.exc_info()[0]))
		
		#clone child-channels
		for child in myChannels[channel]:
			myargs={"name" : "Cloned " + child + " from "+options.targetDate, "label" : options.targetLabel+"-"+options.targetDate+"."+child, "summary" : "Software channel cloned by Satprep", "parent_label": options.targetLabel+"-"+options.targetDate+"."+channel}
			if options.dryrun:
				LOGGER.info("I'd like to clone child-channel '{0}' as '{1}'".format(child, options.targetLabel+"-"+options.targetDate+"."+child))
			else:
				LOGGER.info("Cloning child-channel '{0}' as '{1}'".format(child, options.targetLabel+"-"+options.targetDate+"."+child))
				try:
					result = client.channel.software.clone(key, child, myargs, False)
					if result != 0: LOGGER.debug("Cloned child-channel")
				except xmlrpclib.Fault as e:
					LOGGER.error("Unable to clone base-channel: " + e.faultString)
				except xmlrpclib.ProtocolError as e:
					LOGGER.error("Unable to clone base-channel: " + e.errmsg)
				except: 
					LOGGER.error("Unable to clone child-channel: " + str(sys.exc_info()[0]))



def remapSystems(client, key, unfreeze=False):
	#remap systems
	if options.noRemap: LOGGER.info("Not remapping system's channels")
	else:
		for system in mySystems:
			#remap base-channel
			hostId = client.system.getId(key, system)
			myBase = client.system.getSubscribedBaseChannel(key, hostId[0]["id"])
			if options.unfreeze:
				myNewBase = myBase["label"]
				myNewBase = myNewBase[myNewBase.find(".")+1:]
			else: myNewBase = options.targetLabel+"-"+options.targetDate+"."+myBase["label"]
			
			if options.dryrun: LOGGER.info("I'd like to remap {0}'s base-channel from {1} to {2}".format(system, myBase["label"], myNewBase))
			else:
				try:
					LOGGER.debug("Remapping {0}'s base-channel from {1} to {2}".format(system, myBase["label"], myNewBase))
					result = client.system.setBaseChannel(key, hostId[0]["id"], myNewBase)
					if result == 1: LOGGER.debug("Remapped system")
				except xmlrpclib.Fault as e:
					LOGGER.error("Unable to change base-channel for system '{0}' - '{1} - {2}'".format(system, e.faultCode, e.faultString))
				except:	LOGGER.error("Unable to change base-channel for system '{0}' - '{1}'".format(system, str(sys.exc_info()[0])))
			
			#remap child-channels
			childChannels = client.system.listSubscribedChildChannels(key, hostId[0]["id"])
			tmpChannels=[]
			for channel in childChannels:
				myNewChannel = channel["label"]
				if options.unfreeze:
					#switch back to non-cloned
					myNewChannel = myNewChannel[myNewChannel.find(".")+1:]
				else:
					#switch to cloned
					myNewChannel = options.targetLabel+"-"+options.targetDate+"."+channel["label"]
				tmpChannels.append(myNewChannel)
			if options.dryrun: LOGGER.info("I'd like to set the following child-channels for {0}: {1}".format(system, str(tmpChannels)))
			else:
				try:
					LOGGER.debug("Setting child-channels for {0}: {1}".format(system, str(tmpChannels)))
					result = client.system.setChildChannels(key, hostId[0]["id"], tmpChannels)
				except xmlrpclib.Fault as e:
					#ignore retarded xmlrpclib.Fault as it works like a charm
					pass
				except:
					LOGGER.error("Unable to set child-channels ({0}) for '{1}' - '{2}'".format(str(tmpChannels), system, sys.exc_info()[0]))
			del tmpChannels



def main(options):
	#check/set some necessary information
	if len(options.targetSystems) == 0 and len(options.targetGroups) == 0:
		LOGGER.error("You need to specify at least one system or system group!")
		exit(1)
	if options.targetDate == "wingardiumleviosa":
		#set current date
		now = datetime.datetime.now()
		options.targetDate = now.strftime("%Y-%m-%d")
		LOGGER.debug("Flicked date to: " + now.strftime("%Y-%m-%d"))
	#split label, systems and groups
	options.targetLabel = ''.join(options.targetLabel.split()).strip("-").lower()
	if not "sp" in options.targetLabel: options.targetLabel = "sp-"+options.targetLabel
	if len(options.targetSystems) == 1: options.targetSystems = str(options.targetSystems).strip("[]'").split(",")
	if len(options.targetGroups) == 1: options.targetGroups = str(options.targetGroups).strip("[]'").split(",")
	if len(options.exclude) == 1: options.exclude = str(options.exclude).strip("[]'").split(",")
	
        LOGGER.debug("Options: {0}".format(options))
        LOGGER.debug("Args: {0}".format(args))
	
	#authenticate against Satellite and check whether supported API found
        (username, password) = get_credentials("Satellite", options.authfile)
        satellite_url = "http://{0}/rpc/api".format(options.server)
        client = xmlrpclib.Server(satellite_url, verbose=options.debug)
        key = client.auth.login(username, password)
        check_if_api_is_supported(client)
	
	#get channels
	getChannels(client, key)
	if options.unfreeze:
		remapSystems(client, key, True)
		cloneChannels(client, key, options.targetDate, options.targetLabel, True)
	else:
		cloneChannels(client, key, options.targetDate, options.targetLabel)
		remapSystems(client, key)



def parse_options(args=None):
        if args is None:
                args = sys.argv

        #define description, version and load parser
        desc = '''%prog is used to clone software channels managed with Spacewalk, Red Hat Satellite 5.x and SUSE Manager to freeze system updates. It automatically clones appropriate software channels for particular systems or system groups and also remaps software channels to affected hosts. Login credentials are assigned using the following shell variables:

        SATELLITE_LOGIN  username
        SATELLITE_PASSWORD  password

        It is also possible to create an authfile (permissions 0600) for usage with this script. The first line needs to contain the username, the second line should consist of the appropriate password.
If you're not defining variables or an authfile you will be prompted to enter your login information.

        Checkout the GitHub page for updates: https://github.com/stdevel/satprep'''
        parser = OptionParser(description=desc, version="%prog version 0.3.6")
	#define option groups
	genOpts = OptionGroup(parser, "Generic Options")
	srvOpts = OptionGroup(parser, "Server Options")
	sysOpts = OptionGroup(parser, "System Options")
	chnOpts = OptionGroup(parser, "Channel Options")
	parser.add_option_group(genOpts)
	parser.add_option_group(srvOpts)
	parser.add_option_group(sysOpts)
	parser.add_option_group(chnOpts)
	
	#GENERIC OPTIONS
	#-d / --debug
	genOpts.add_option("-d", "--debug", dest="debug", default=False, action="store_true", help="enable debugging outputs (default: no)")
	#-n / --dry-run
	genOpts.add_option("-n", "--dry-run", action="store_true", dest="dryrun", default=False, help="only simulates the creation of custom keys (default: no)")
	#-u / --unfreeze
	genOpts.add_option("-u", "--unfreeze", action="store_true", dest="unfreeze", default=False, help="removes clones and remaps systems (default: no)")
	
	#SERVER OPTIONS
	#-a / --authfile
	srvOpts.add_option("-a", "--authfile", dest="authfile", metavar="FILE", default="", help="defines an auth file to use instead of shell variables")
	#-s / --server
	srvOpts.add_option("-s", "--server", dest="server", metavar="SERVER", default="localhost", help="defines the server to use (default: localhost)")
	
	#SYSTEM OPTIONS
	#-S / --system
	sysOpts.add_option("-S", "--system", action="append", dest="targetSystems", metavar="SYSTEM", type="string", default=[], help="specifies a system to use for freezing patches")
	#-g / --group
	sysOpts.add_option("-g", "--group", action="append", dest="targetGroups", metavar="GROUP", type="string", default=[], help="specifies a system group to use for freezing patches")
	#-e / --exclude
	sysOpts.add_option("-e", "--exclude", action="append", dest="exclude", metavar="SYSTEM", type="string", default=[], help="defines hosts that should be excluded for freezing patches")
	#-i / --no-remap
	sysOpts.add_option("-i", "--no-remap", action="store_true", dest="noRemap", default=False, help="disables remapping affected systems to cloned channels (default: no)")
	
	#CHANNEL OPTIONS
	#-A / --all-subchannels
	chnOpts.add_option("-A", "--all-subchannels", action="store_true", dest="allSubchannels", default=False, help="clones all sub-channels instead of only required ones (default: no)")
	#-l / --label
	chnOpts.add_option("-l", "--label", action="store", dest="targetLabel", metavar="LABEL", default="sp", help="defines a label for the cloned channel (e.g. application name)")
	#-D / --date
	chnOpts.add_option("-D", "--date", action="store", dest="targetDate", metavar="DATE", default="wingardiumleviosa", help="defines the date patches should be freezed (default: current date)")
	
        (options, args) = parser.parse_args(args)
        return (options, args)



if __name__ == "__main__":
        (options, args) = parse_options()

        if options.debug:
                logging.basicConfig(level=logging.DEBUG)
                LOGGER.setLevel(logging.DEBUG)
        else:
                logging.basicConfig()
                LOGGER.setLevel(logging.INFO)

        main(options)
