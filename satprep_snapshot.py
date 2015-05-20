#!/usr/bin/env python
# -*- coding: utf-8 -*-

# satprep_snapshot.py - a script for creating a snapshot
# report of available errata available to systems managed
# with Spacewalk, Red Hat Satellite or SUSE Manager.
#
# 2015 By Christian Stankowic
# <info at stankowic hyphen development dot net>
# https://github.com/stdevel
#

import csv
import logging
import os
import sys
import time
import xmlrpclib
from optparse import OptionParser, OptionGroup
from satprep_shared import check_if_api_is_supported, get_credentials
from unidecode import unidecode



#define fields, previously it was possible to define custom fields
POSSIBLE_FIELDS = ["hostname", "ip", "errata_name", "errata_type",
	 "errata_desc", "errata_date", "errata_reboot", "system_owner", "system_prod",
	 "system_cluster", "system_virt", "system_virt_snapshot", "system_virt_vmname",
 	 "system_monitoring", "system_monitoring_name", "system_monitoring_notes",
	 "system_backup", "system_backup_notes", "system_antivir", "system_antivir_notes"
 ]
DEFAULT_FIELDS = POSSIBLE_FIELDS
LOGGER = logging.getLogger('satprep-snapshot')



def parse_options(args=None):
	if args is None:
		args = sys.argv

	desc='''%prog is used to create snapshot CSV reports of errata available to your systems managed with Spacewalk, Red Hat Satellite and SUSE Manager. You can use two snapshot reports to create delta reports using satprep_diff.py. Login credentials are assigned using the following shell variables:

SATELLITE_LOGIN  username
SATELLITE_PASSWORD  password

It is also possible to create an authfile (permissions 0600) for usage with this script. The first line needs to contain the username, the second line should consist of the appropriate password.
If you're not defining variables or an authfile you will be prompted to enter your login information.

Checkout the GitHub page for updates: https://github.com/stdevel/satprep'''
	parser = OptionParser(description=desc, version="%prog version 0.3.3")
	#define option groups
	genOpts = OptionGroup(parser, "Generic Options")
	parser.add_option_group(genOpts)
	srvOpts = OptionGroup(parser, "Server Options")
	parser.add_option_group(srvOpts)
	snapOpts = OptionGroup(parser, "Snapshot Options")
	parser.add_option_group(snapOpts)
	
	#GENERIC OPTIONS
	#-q / --quiet
	genOpts.add_option("-q", "--quiet", action="store_false", dest="verbose", default=True, help="don't print status messages to stdout (default: no)")
	#-d / --debug
	genOpts.add_option("-d", "--debug", dest="debug", default=False, action="store_true", help="enable debugging outputs (default: no)")
	
	#SERVER OPTIONS
	#-a / --authfile
	srvOpts.add_option("-a", "--authfile", dest="authfile", metavar="FILE", default="", help="defines an auth file to use instead of shell variables")
	#-s / --server
	srvOpts.add_option("-s", "--server", dest="server", metavar="SERVER", default="localhost", help="defines the server to use (default: localhost)")
	#-r / --reconnect-threshold
	srvOpts.add_option("-r", "--reconnect-threshold", action="store", type="int", default=5, dest="reconnectThreshold", metavar="THRESHOLD", help="defines after how many host scans a re-login should be done (XMLRPC API timeout workaround, default: 5)")
	
	#SNAPSHOT OPTIONS
	#-o / --output
	snapOpts.add_option("-o", "--output", action="store", type="string", dest="output", default="foobar", metavar="FILE", help=("define CSV report filename. (default: " "errata-snapshot-report-RHNhostname-Ymd.csv)"))
	#-f / --field
	#snapOpts.add_option("-f", "--field", action="append", type="choice", dest="fields", choices=POSSIBLE_FIELDS, metavar="FIELDS", help="defines which fields should be integrated in the report (default: all available)")
	#-p / --include-patches
	snapOpts.add_option("-p", "--include-patches", action="store_true", default=False, dest="includePatches", help="defines whether package updates that are not part of an erratum shall be included (default: no)")
	#-l / --include-locked
	snapOpts.add_option("-l", "--include-locked", action="store_true", default=False, dest="includeLocked", help="also includes locked systems (default: no)")

	(options, args) = parser.parse_args(args)

	if options.output is 'foobar':
		options.output = "errata-snapshot-report-{server}-{time}.csv".format(
			server=options.server,
			time=time.strftime("%Y%m%d-%H%M")
		)

	LOGGER.debug("Options: {0}".format(options))
	LOGGER.debug("Arguments: {0}".format(args))
	
	return (options, args)



def main(options):
	(username, password) = get_credentials("Satellite", options.authfile)

	sattelite_url = "http://{0}/rpc/api".format(options.server)
	client = xmlrpclib.Server(sattelite_url, verbose=options.debug)
	key = client.auth.login(username, password)
	check_if_api_is_supported(client)
	
	if options.includeLocked: LOGGER.warning("Snapshot report will also include information about locked systems")

	#check whether the output directory/file is writable
	if os.access(os.path.dirname(options.output), os.W_OK) or os.access(os.getcwd(), os.W_OK):
		LOGGER.debug("Output file/directory writable!")

		#create CSV report, open file
		csv.register_dialect("default", delimiter=";", quoting=csv.QUOTE_NONE)
		writer = csv.writer(open(options.output, "w"), 'default')

		#create header and scan _all_ the systems
		writer.writerow(DEFAULT_FIELDS)
		systems = client.system.listSystems(key)
		#counter variable for XMLRPC timeout workaround (https://github.com/stdevel/satprep/issues/5)
		hostCounter = 0
		for system in systems:
			process_system(client, key, writer, system)

			#increase counter and re-login if necessary
			if hostCounter == (options.reconnectThreshold-1):
				#re-login
				LOGGER.debug("Re-login due to XMLRPC timeout workaround!")
				client.auth.logout(key)
				key = client.auth.login(username, password)
				hostCounter = 0
			else:
				#increase counter
				hostCounter = hostCounter + 1

	else:
		#output file/directory not writable
		LOGGER.critical("Output file/directory ({0}) not writable".format(options.output))

	#logout and exit
	client.auth.logout(key)



def process_system(client, key, writer, system):
	LOGGER.debug("Found host {0[name]} (SID {0[id]})".format(system))
	process_errata(client, key, writer, system)

	if options.includePatches:
		process_patches(client, key, writer, system)



def process_errata(client, key, writer, system):
	columnErrataMapping = {
		"hostname": "name",
		"errata_name": "advisory_name",
		"errata_type": "advisory_type",
		"errata_desc": "advisory_synopsis",
		"errata_date": "update_date"
	}
	
	#break if system locked
	details = client.system.getDetails(key, system["id"])
	if details["lock_status"] != False and options.includeLocked == False:
		LOGGER.info("Skipping errata for locked host "
			"{system[name]} (SID {system[id]})...".format(
				system=system
			)
		)
		return
	
	#TODO: errata_* not working! Implemented a workaround (looking for a "nicer" way to do this)
	
	errata = client.system.getRelevantErrata(key, system["id"])
	if not errata:
		LOGGER.debug("Host {0[name]} (SID {0[id]}) has no relevant errata.".format(system))
		return
	else:
		LOGGER.info("Looking at relevant errata for host "
			"{system[name]} (SID {system[id]})...".format(
				system=system
			)
		)

	for i, erratum in enumerate(errata, start=1):
		LOGGER.debug("Having a look at relevant errata #{errata} "
			"for host {system[name]} (SID {system[id]})...".format(
				errata=i,
				system=system
			)
		)
		
		valueSet = []
		for column in DEFAULT_FIELDS:
			try:
				valueSet.append(system[columnErrataMapping[column]])
				LOGGER.debug("Translated column '" + column + "' in '" + columnErrataMapping[column] + "'") 
				continue
			except KeyError:
				#Key not found - probably needs more logic.
				LOGGER.debug("Could not find column '" + column + "' in columnErrataMapping")
				pass
			
			if column == "ip":
				temp = client.system.getNetwork(key, system["id"])
				valueSet.append(temp["ip"])
			
			###WORKAROUND###
			elif column == "errata_name":
				try:
					valueSet.append(errata[i]["advisory_name"])
				except:
					valueSet.append("")
			elif column == "errata_type":
				try:
					valueSet.append(errata[i]["advisory_type"])
				except:
					valueSet.append("")
			elif column == "errata_desc":
				try:
					valueSet.append(errata[i]["advisory_synopsis"])
				except:
					valueSet.append("")
			elif column == "errata_date":
				try:
					valueSet.append(errata[i]["update_date"])
				except:
					valueSet.append("")
			###END WORKAROUND###
			
			elif column == "errata_reboot":
				try:
					if "kernel" in errata[i]["advisory_synopsis"]:
						valueSet.append("1")
					else:
						temp = client.errata.listKeywords(key, errata[i]["advisory_name"])
						if "reboot_suggested" in temp:
							valueSet.append("1")
						else:
							valueSet.append("0")
				except:
					valueSet.append("0")
			elif column == "system_owner":
				temp = client.system.getCustomValues(key, system["id"])
				if temp and "SYSTEM_OWNER" in temp:
					valueSet.append(' '.join(temp["SYSTEM_OWNER"].split()))
				else:
					valueSet.append("unknown")
			elif column == "system_prod":
				temp = client.system.getCustomValues(key, system["id"])
				if (temp and "SYSTEM_PROD" in temp
					and temp["SYSTEM_PROD"] == "1"):
					valueSet.append(1)
				else:
					valueSet.append(0)
			elif column == "system_cluster":
				temp = client.system.getCustomValues(key, system["id"])
				if (temp and "SYSTEM_CLUSTER" in temp
					and temp["SYSTEM_CLUSTER"] == "1"):
					valueSet.append(1)
				else:
					valueSet.append(0)
			elif column == "system_virt":
				temp = client.system.getDetails(key, system["id"])
				if temp and "virtualization" in temp:
					valueSet.append(1)
				else:
					valueSet.append(0)
			elif column == "system_virt_snapshot":
                        	temp = client.system.getCustomValues(key, system["id"])
                                if (temp and "SYSTEM_VIRT_SNAPSHOT" in temp
                                        and temp["SYSTEM_VIRT_SNAPSHOT"] == "1"):
                                        valueSet.append(1)
                                else:
                                        valueSet.append(0)
			elif column == "system_virt_vmname":
                        	temp = client.system.getCustomValues(key, system["id"])
				temp_vmname=""
                                if (temp and "SYSTEM_VIRT_VMNAME" in temp
                                        and temp["SYSTEM_VIRT_VMNAME"] != ""):
					temp_vmname=temp["SYSTEM_VIRT_VMNAME"]
					#also add custom host and password if given
					if (temp and "SYSTEM_VIRT_HOST" in temp
					and temp["SYSTEM_VIRT_HOST"] != "" and
					"SYSTEM_VIRT_HOST_AUTH" in temp and
					temp["SYSTEM_VIRT_HOST_AUTH"] != ""):
						temp_vmname = temp_vmname + "@" + temp["SYSTEM_VIRT_HOST"] + ":" + temp["SYSTEM_VIRT_HOST_AUTH"]
                                        valueSet.append(temp_vmname)
				else: valueSet.append("")
			elif column == "system_monitoring":
				temp = client.system.getCustomValues(key, system["id"])
				if (temp and "SYSTEM_MONITORING" in temp and
					temp["SYSTEM_MONITORING"] == "1"):
					valueSet.append(1)
				else:
					valueSet.append(0)
			elif column == "system_monitoring_name":
				temp = client.system.getCustomValues(key, system["id"])
				temp_monname = ""
				if (temp and "SYSTEM_MONITORING_NAME" in temp
					and temp["SYSTEM_MONITORING_NAME"] != ""):
					temp_monname=temp["SYSTEM_MONITORING_NAME"]
					#also add custom host and password if given
					if (temp and "SYSTEM_MONITORING_HOST" in temp
					and temp["SYSTEM_MONITORING_HOST"] != "" and
					"SYSTEM_MONITORING_HOST_AUTH" in temp and
					temp["SYSTEM_MONITORING_HOST_AUTH"] != ""):
						temp_monname = temp_monname + "@" + temp["SYSTEM_MONITORING_HOST"] + ":" + temp["SYSTEM_MONITORING_HOST_AUTH"]
					valueSet.append(temp_monname)
				else:
					valueSet.append("")
			elif column == "system_monitoring_notes":
				temp = client.system.getCustomValues(key, system["id"])
				if temp and "SYSTEM_MONITORING_NOTES" in temp:
					valueSet.append(temp["SYSTEM_MONITORING_NOTES"])
				else:
					valueSet.append("")
			elif column == "system_backup":
				temp = client.system.getCustomValues(key, system["id"])
				if (temp and "SYSTEM_BACKUP" in temp
					and temp["SYSTEM_BACKUP"] == "1"):
					valueSet.append(1)
				else:
					valueSet.append(0)
			elif column == "system_backup_notes":
				temp = client.system.getCustomValues(key, system["id"])
				if temp and "SYSTEM_BACKUP_NOTES" in temp:
					valueSet.append(temp["SYSTEM_BACKUP_NOTES"])
				else:
					valueSet.append("")
			elif column == "system_antivir":
				temp = client.system.getCustomValues(key, system["id"])
				if (temp and "SYSTEM_ANTIVIR" in temp
					and temp["SYSTEM_ANTIVIR"] == "1"):
					valueSet.append(1)
				else:
					valueSet.append(0)
			elif column == "system_antivir_notes":
				temp = client.system.getCustomValues(key, system["id"])
				if temp and "SYSTEM_ANTIVIR_NOTES" in temp:
					valueSet.append(temp["SYSTEM_ANTIVIR_NOTES"])
				else:
					valueSet.append("")

		#replace unicodes
		for i,field in enumerate(valueSet):
			if type(field) is unicode:
				LOGGER.debug("Converted to ascii: {ascii}".format(
					ascii=unidecode(field)
				))
				valueSet[i] = str(unidecode(field))
		
		writer.writerow(valueSet)



def process_patches(client, key, writer, system):
	updates = client.system.listLatestUpgradablePackages(key, system["id"])

	#break if system locked
	details = client.system.getDetails(key, system["id"])
	if details["lock_status"] != False and options.includeLocked == False:
		LOGGER.info("Skipping patches for locked host "
			"{system[name]} (SID {system[id]})...".format(
				system=system
			)
		)
		return
	
	if not updates:
		LOGGER.debug("Host {0[name]} (SID {0[id]}) has no relevant updates.".format(system))
		return
	else:
		LOGGER.info("Looking at relevant package updates for host "
			"{system[name]} (SID {system[id]})...".format(
				system=system
			)
		)

	for i, update in enumerate(updates, start=1):
		LOGGER.debug("Having a look at relevant package update "
			"#{update} for host {system[name]} "
			"(SID {system[id]})...".format(
				update=i,
				system=system
			)
		)
		
		if client.packages.listProvidingErrata(key, update["to_package_id"]):
			#We only add update information if it is not not
			#already displayed as part of an erratum
			LOGGER.debug("Dropping update {0[name]} "
				"({0[to_package_id]}) as it's already part of "
				"an erratum.".format(update)
			)
			continue

		valueSet = []
		for column in DEFAULT_FIELDS:
			if column == "hostname":
				valueSet.append(system["name"])
			elif column == "ip":
				temp = client.system.getNetwork(key, system["id"])
				valueSet.append(temp["ip"])
			elif column == "errata_name":
				valueSet.append(update["name"])
			elif column == "errata_type":
				valueSet.append("Regular update")
			elif column == "errata_desc":
				valueSet.append("{0[from_version]}-{0[from_release]} to {0[to_version]}-{0[to_release]}".format(update))
			elif column == "errata_date":
				valueSet.append("unknown")
			elif column == "errata_reboot":
				if "kernel" in update["name"]:
					valueSet.append("1")
				else:
					valueSet.append("0")
			elif column == "system_owner":
				temp = client.system.getCustomValues(key, system["id"])
				if temp and "SYSTEM_OWNER" in temp:
					valueSet.append(' '.join(temp["SYSTEM_OWNER"].split()))
				else:
					valueSet.append("unknown")
			elif column == "system_prod":
				temp = client.system.getCustomValues(key, system["id"])
				if (temp and "SYSTEM_PROD" in temp
					and temp["SYSTEM_PROD"] == "1"):
					valueSet.append(1)
				else:
					valueSet.append(0)
			elif column == "system_cluster":
				temp = client.system.getCustomValues(key, system["id"])
				if (temp and "SYSTEM_CLUSTER" in temp
					and temp["SYSTEM_CLUSTER"] == "1"):
					valueSet.append(1)
				else:
					valueSet.append(0)
			elif column == "system_virt":
				temp = client.system.getDetails(key, system["id"])
				if temp and "virtualization" in temp:
					valueSet.append(1)
				else:
					valueSet.append(0)
                        elif column == "system_virt_snapshot":
                                temp = client.system.getCustomValues(key, system["id"])
                                if (temp and "SYSTEM_VIRT_SNAPSHOT" in temp
                                        and temp["SYSTEM_VIRT_SNAPSHOT"] == "1"):
                                        valueSet.append(1)
                                else:
                                        valueSet.append(0)
			elif column == "system_virt_vmname":
                        	temp = client.system.getCustomValues(key, system["id"])
				temp_vmname=""
                                if (temp and "SYSTEM_VIRT_VMNAME" in temp
                                        and temp["SYSTEM_VIRT_VMNAME"] != ""):
					temp_vmname=temp["SYSTEM_VIRT_VMNAME"]
					#also add custom host and password if given
					if (temp and "SYSTEM_VIRT_HOST" in temp
					and temp["SYSTEM_VIRT_HOST"] != "" and
					"SYSTEM_VIRT_HOST_AUTH" in temp and
					temp["SYSTEM_VIRT_HOST_AUTH"] != ""):
						temp_vmname = temp_vmname + "@" + temp["SYSTEM_VIRT_HOST"] + ":" + temp["SYSTEM_VIRT_HOST_AUTH"]
                                        valueSet.append(temp_vmname)
				else: valueSet.append("")
			elif column == "system_monitoring":
				temp = client.system.getCustomValues(key, system["id"])
				if (temp and "SYSTEM_MONITORING" in temp and
					temp["SYSTEM_MONITORING"] == "1"):
					valueSet.append(1)
				else:
					valueSet.append(0)
			elif column == "system_monitoring_name":
				temp = client.system.getCustomValues(key, system["id"])
				temp_monname = ""
				if (temp and "SYSTEM_MONITORING_NAME" in temp
					and temp["SYSTEM_MONITORING_NAME"] != ""):
					temp_monname=temp["SYSTEM_MONITORING_NAME"]
					#also add custom host and password if given
					if (temp and "SYSTEM_MONITORING_HOST" in temp
					and temp["SYSTEM_MONITORING_HOST"] != "" and
					"SYSTEM_MONITORING_HOST_AUTH" in temp and
					temp["SYSTEM_MONITORING_HOST_AUTH"] != ""):
						temp_monname = temp_monname + "@" + temp["SYSTEM_MONITORING_HOST"] + ":" + temp["SYSTEM_MONITORING_HOST_AUTH"]
					valueSet.append(temp_monname)
				else:
					valueSet.append("")
			elif column == "system_monitoring_notes":
				temp = client.system.getCustomValues(key, system["id"])
				if temp and "SYSTEM_MONITORING_NOTES" in temp:
					valueSet.append(temp["SYSTEM_MONITORING_NOTES"])
				else:
					valueSet.append("")
			elif column == "system_backup":
				temp = client.system.getCustomValues(key, system["id"])
				if (temp and "SYSTEM_BACKUP" in temp
					and temp["SYSTEM_BACKUP"] == "1"):
					valueSet.append(1)
				else:
					valueSet.append(0)
			elif column == "system_backup_notes":
				temp = client.system.getCustomValues(key, system["id"])
				if temp and "SYSTEM_BACKUP_NOTES" in temp:
					valueSet.append(temp["SYSTEM_BACKUP_NOTES"])
				else:
					valueSet.append("")
			elif column == "system_antivir":
				temp = client.system.getCustomValues(key, system["id"])
				if (temp and "SYSTEM_ANTIVIR" in temp
					and temp["SYSTEM_ANTIVIR"] == "1"):
					valueSet.append(1)
				else:
					valueSet.append(0)
			elif column == "system_antivir_notes":
				temp = client.system.getCustomValues(key, system["id"])
				if temp and "SYSTEM_ANTIVIR_NOTES" in temp:
					valueSet.append(temp["SYSTEM_ANTIVIR_NOTES"])
				else:
					valueSet.append("")

		if valueSet:
			writer.writerow(valueSet)



if __name__ == "__main__":
	(options, args) = parse_options()

	if options.debug:
		logging.basicConfig(level=logging.DEBUG)
		LOGGER.setLevel(logging.DEBUG)
	else:
		logging.basicConfig()
		LOGGER.setLevel(logging.INFO)

	main(options)
