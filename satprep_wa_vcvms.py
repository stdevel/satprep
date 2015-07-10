#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import sys
import xmlrpclib
from optparse import OptionParser, OptionGroup
from satprep_shared import check_if_api_is_supported, get_credentials
from pysphere import VIServer



#some global variables
host_vms={}
hosts_by_dc = {}
hosts_by_cluster = {}
satellite_vmtypes=["Red Hat Enterprise", "CentOS", "SUSE", "openSUSE", "Debian", "Ubuntu", "Solaris", "Fedora"]

#set logger
LOGGER = logging.getLogger('satprep_wa_vcvms')

def main(options):
	global host_vms
	LOGGER.debug("Options: {0}".format(options))
	LOGGER.debug("Args: {0}".format(args))
	
	#check for senseful inputs
	if not options.vcServer or not options.satServer:
		LOGGER.error("You need to specify at least Satellite and vCenter hostnames!")
		exit(1)
	
	#get Satellite and vCenter credentials
	if options.dryrun: LOGGER.info("I'm only doing a simulation, I promise!")
	(satUsername, satPassword) = get_credentials("Satellite", options.satAuthfile)
	(vcUsername, vcPassword) = get_credentials("Virtualization", options.vcAuthfile)
	
	#connect to vCenter
	myVC = VIServer()
	myVC.connect(options.vcServer, vcUsername, vcPassword)
	
	#connect to Satellite
	satellite_url = "http://{0}/rpc/api".format(options.satServer)
	mySat = xmlrpclib.Server(satellite_url, verbose=options.debug)
	key = mySat.auth.login(satUsername, satPassword)
	check_if_api_is_supported(mySat)
	
	#print information about host
	LOGGER.info("Connected to " + options.vcServer + " (" + myVC.get_server_type() + "), version " + myVC.get_api_version() + ".")
	
	#get list of all ESXi hosts by datacenter
	LOGGER.info("Searching for ESXi hosts by datacenter...")
	esxiHosts = myVC.get_hosts()
	datacenters = myVC.get_datacenters()
	for dc in datacenters:
		tempHosts = myVC.get_hosts(from_mor=dc).values()
		hosts_by_dc[datacenters.get(dc)] = (tempHosts)
	LOGGER.debug("Hosts by DC: " + str(hosts_by_dc))
	
	#get list of all ESXi hosts by cluster
	LOGGER.info("Searching for ESXi hosts by cluster...")
	clusters = myVC.get_clusters()
	for cluster in clusters:
		tempHosts = myVC.get_hosts(from_mor=cluster).values()
		hosts_by_cluster[clusters.get(cluster)] = (tempHosts)
	LOGGER.debug("Hosts by cluster: " + str(hosts_by_cluster))
	
	#get list of all VMs by ESXi host
	for dc in datacenters:
		for host in hosts_by_dc[datacenters.get(dc)]:
			LOGGER.debug("Found ESXi host '" + host + "'")
			host_vms[host]=[]
	LOGGER.debug("Added hosts to dict: " + str(host_vms))
	
	#get list of all Linux VMs managed by Satellite
	satlist = mySat.system.listSystems(key)
	target_vms=[]
	LOGGER.info("Digging through list of systems managed by Satellite...")
	for system in satlist:
		LOGGER.debug("Found system '" + system["name"] + "'")
		#get custom keys
		thisKeys = mySat.system.getCustomValues(key, system["id"])
		#add virt_vmname if given
		if "SYSTEM_VIRT_VMNAME" in thisKeys and thisKeys["SYSTEM_VIRT_VMNAME"] != "":
			target_vms.append(thisKeys["SYSTEM_VIRT_VMNAME"])
		else: target_vms.append(system)
		LOGGER.debug("VM names: " + str(target_vms))
	
	#get list of all VMs and assign to host dicts
	LOGGER.info("Getting list of all VMs and assign them to host arrays - grab some coffee.")
	vmlist = myVC.get_registered_vms()
	counter=0
	hit=0
	for vm in vmlist:
		#get VM and its properties
		thisVM = myVC.get_vm_by_path(vm)
		#only add if in target_vms
		if thisVM.properties.name in target_vms:
			LOGGER.debug("Found VM managed by Satellite: '" + thisVM.properties.name + "'")
			host_vms[thisVM.properties.runtime.host.name].append(thisVM.properties.name)
		else: LOGGER.debug("'" + thisVM.properties.name + "' dropped as it is not managed by Satellite")
		
		LOGGER.debug("Current array for host '" + thisVM.properties.runtime.host.name + "': " + str(host_vms[thisVM.properties.runtime.host.name]))
		#show progress
		if hit == 9:
			LOGGER.info("Checked " + str(counter+1) + " of " + str(len(vmlist)) + " VMs so far...")
			hit=0
		else: hit=(hit+1)
		counter=(counter+1)
	LOGGER.debug("Added VMs to host dicts: " + str(host_vms))
	
	#get list of all Linux VMs managed by Satellite
	satlist = mySat.system.listSystems(key)
	LOGGER.info("Updating relevant system custom info keys...")
	for system in satlist:
		LOGGER.debug("Found system '" + system["name"] + "'")
		#get custom keys
		thisKeys = mySat.system.getCustomValues(key, system["id"])
		#update key if exists
		if "SYSTEM_VIRT_HOST" in thisKeys and thisKeys["SYSTEM_VIRT_HOST"] != "":
			#get ESXi host running VM
			if "SYSTEM_VIRT_VMNAME" in thisKeys and thisKeys["SYSTEM_VIRT_VMNAME"] != "":
				this_ESXi = get_ESXi_host_by_vm(thisKeys["SYSTEM_VIRT_VMNAME"])
			else: this_ESXi = get_ESXi_host_by_vm(system["name"])
			#get cluster if applicable
			this_cluster = get_cluster_by_ESXi_host(this_ESXi)
			#update custom key
			if this_cluster != "":
				#cluster
				this_value = "vpx://" + options.vcServer + "/" + get_datacenter_by_ESXi_host(this_ESXi) + "/" + this_cluster + "/" + this_ESXi
			else:
				#no cluster
				this_value = "vpx://" + options.vcServer + "/" + get_datacenter_by_ESXi_host(this_ESXi) + "/" + this_ESXi
			if options.vcVerify == False: this_value = this_value + "?no_verify=1"
			if options.dryrun:
				if this_ESXi != "": LOGGER.info("I'd like to set SYSTEM_VIRT_HOST='" + this_value + "' for system '" + system["name"] + "' (ID " + str(system["id"]) + ")")
				else: LOGGER.error("No valid virt host entry for system '" + system["name"] + "' (ID " + str(system["id"]) + ") found!")
			else:
				#update customkey if not null
				if this_ESXi != "":
					if mySat.system.setCustomValues(key, system["id"], {"SYSTEM_VIRT_HOST": this_value}):
						LOGGER.info("Updated virtual host entry for system '" + system["name"] + "' (ID " + str(system["id"]) + ").")
				else: LOGGER.error("No valid virt host entry for system '" + system["name"] + "' (ID " + str(system["id"]) + ") found!")



#check whether OS type is managed by Satellite
def is_satellite_managed(name):
	global satellite_vmtypes
	
	#scan all manageable VM types
	for i in satellite_vmtypes:
		#return true if found
		if i.lower() in name.lower(): return True
	return False



#get datacenter by ESXi host
def get_datacenter_by_ESXi_host(host):
	global hosts_by_dc
	
	#scan all dc
	for dc in hosts_by_dc:
		hosts = hosts_by_dc[dc]
		if host in hosts: return dc
	return ""



#get cluster by ESXi host
def get_cluster_by_ESXi_host(host):
	global hosts_by_cluster
	
	#scan all clusters
	for cluster in hosts_by_cluster:
		hosts = hosts_by_cluster[cluster]
		if host in hosts: return cluster
	return ""



#get ESXi host running a particular VM
def get_ESXi_host_by_vm(vm):
	global host_vms
	
	#scan all hosts in dict
	for host in host_vms:
		vmlist = host_vms.get(host)
		#return hostname if found
		if vm in vmlist: return str(host)
	return ""



def parse_options(args=None):
	if args is None:
		args = sys.argv
	# define description, version and load parser
	desc = '''%prog is used to assign currently used VMware vSphere compute ressources (vDC, cluster, ESXi host) to custominfo keys for systems managed with Spacewalk, Red Hat Satellite or SUSE Manager. As libvirt currently does not support accessing vCenter without specifying dedicated ESXi hosts this is needed if you plan to create snapshots using satprep while having fully-automatic vSphere DRS activated. Login credentials are assigned using the following shell variables:
	SATELLITE_LOGIN Satellite username
	SATELLITE_PASSWORD Satellite password
	VIRTUALIZATION_LOGIN vCenter username
	VIRTUALIZATION_LOGIN vCenter password
	It is also possible to create an authfile (permissions 0600) for usage with this script (parameters -a/-A). The first line needs to contain the username, the second line should consist of the appropriate password.
	If you're not defining variables or an authfile you will be prompted to enter your login information.
	Checkout the GitHub wiki for further information: https://github.com/stdevel/satprep/wiki'''
	parser = OptionParser(description=desc, version="%prog version 0.3.4")
	
	#define option groups
	genOpts = OptionGroup(parser, "Generic Options")
	satOpts = OptionGroup(parser, "Satellite Options")
	vcOpts = OptionGroup(parser, "vCenter Options")
	parser.add_option_group(genOpts)
	parser.add_option_group(satOpts)
	parser.add_option_group(vcOpts)
	
	#GENERIC OPTIONS
	#-d / --debug
	genOpts.add_option("-d", "--debug", dest="debug", default=False, action="store_true", help="enable debugging outputs (default: no)")
	#-n / --dry-run
	genOpts.add_option("-n", "--dry-run", action="store_true", dest="dryrun", default=False, help="only simulates updating custom keys (default: no)")
	
	#SATELLITE OPTIONS
	#-a / --satellite-authfile
	satOpts.add_option("-a", "--satellite-authfile", dest="satAuthfile", metavar="FILE", default="", help="defines an auth file to use for Satellite")
	#-s / --satellite-server
	satOpts.add_option("-s", "--satellite-server", dest="satServer", metavar="SERVER", default="localhost", help="defines the Satellite server to use (default: localhost)")
	
	#VCENTER OPTIONS
	#-A / --vcenter-authfile
	vcOpts.add_option("-A", "--vcenter-authfile", dest="vcAuthfile", metavar="FILE", default="", help="defines an auth file to use for VMware vCenter")
	#-S / --vcenter-server
	vcOpts.add_option("-S", "--vcenter-server", dest="vcServer", metavar="SERVER", default="", help="defines the VMware vCenter server to use")
	#-v / --verify-ssl
	vcOpts.add_option("-v", "--verify-ssl", dest="vcVerify", metavar="BOOL", default=False, help="forces using verified SSL connections (removes libvirt ?no_verify=1 flag, default: no)")
	
	#parse and return options
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
