satprep
=======

**satprep** is a Python toolkit for automating system maintenance and generating CSV/PDF patch reports for systems managed with [Spacewalk](http://www.spacewalkproject.org/), [Red Hat Satellite](http://www.redhat.com/products/enterprise-linux/satellite/) or [SUSE Manager](http://www.suse.com/products/suse-manager/).
 
This can be very useful if you need to document software changes due to IT certifications like [ISO/IEC 27001:2005](http://en.wikipedia.org/wiki/ISO/IEC_27001:2005) or many other.

After doing maintenance tasks this toolkit can create detailed change reports per host. Before starting maintenance  you can also automate scheduling downtime for your systems and creating VM snapshots.



Supported software
==================
The following monitoring suites are supported:
- [Nagios](http://www.nagios.org/)
- [Icinga](http://www.icinga.org/)
- [Thruk](http://www.thruk.org/)
- [Shinken](http://www.shinken-monitoring.org)
- course this also works in combination with the Swiss Army knife [OMD](http://www.omdistro.org).

As this toolkit uses the Python bindings of [libvirt](http://www.libvirt.org) a wide range of Hypervisors can be used - including:
- KVM/Qemu
- Xen
- VMware vSphere ESXi
- Microsoft Hyper-V
- ...and many more



What does a report look like?
=============================
A maintenance report looks like this:
![Example satprep maintenance report](https://raw.githubusercontent.com/stdevel/satprep/master/satprep_example_report.png "Example satprep maintenance report")



How does it work?
=================
The toolkit consists of four scripts:

1. `satprep_install_custominfo.py` - installs necessary custom information (*see above*) for your hosts managed with Spacewalk, Red Hat Satellite or SUSE Manager. You will need to execute this script once to make sure that all information can be assigned
2. `satprep_snapshot.py` - creates an inventory of the current available patches and errata to your system landscape. It gathers the following information:
  * system hostname and IP
  * system virtualization guest status
  * system owner / cluster member / monitoring / backup / anti-virus status (*optional*)
  * errata information including name, date, description, advisory type (*security/bugfix/enhancement update*) and even whether a reboot is required
  * also regular patch information (*optional*)
4. `satprep_prepare_maintenance.py` - schedules monitoring downtimes and creates VM snapshots, also makes sure that all required preparations are done before you begin with your work
3. `satprep_diff.py` - creates the delta, required to create the maintenance reports



Make sure to follow this procedure to document your maintenance tasks:
1. do a complete patch/errata inventory of your landscape: `./satprep_snapshot.py`
2. notice that a CSV report was created: `errata-snapshot-report-$RHNhostname-YYYYMMDD-HHMM.csv`
3. prepare maintenance; automatically create VMware snapshots and monitoring downtimes and verify them: `./satprep_prepare_maintenance.py snapshot.csv ; ./satprep_prepary_maintenance.py -V snapshot.csv` (*optional*)
4. complete your system maintenance tasks (*patch and reboot systems, etc.*)
5. do another complete patch/errata inventory: `./satprep_snapshot.py`
6. create a difference report and host reports: `./satprep_diff.py *.csv`

Afterwards the reports are stored in `/tmp`.

For gathering optional semantic information (*e.g. backup and monitoring*) the script makes usage of the **custom system information** feature of Spacewalk, Red Hat Satellite or SUSE Manager. After installing the custom keys using the `satprep_install_custominfo.py` utility you can assign the following information per host (*only a selection*):
* **SYSTEM_OWNER** - server responsible in your team
* **SYSTEM_MONITORING** - monitoring state (*0 or empty = disabled, 1 = enabled*))
* **SYSTEM_BACKUP** - defines whether the host is protected using backups (*0 or empty = no, 1 = yes*)
* **SYSTEM_ANTIVIR** - defines whether the host is protected against viruses (*0 or empty = no, 1 = yes*)

See the [wiki](https://github.com/stdevel/satprep/wiki) for more details about the particular scripts.



Requirements
============
**satprep** needs Python 2.6 or newer - it runs on EL5/6 machines without adding additional software repositories.
The following additional Python modules are used:
* libvirt
* xmlrpclic (*shipped with `rhnlib`*)
* requests

The toolkit needs the `pdflatex` binary which is usually part of the LaTeX or TeX Live software set provided by your distributor.

Check out the [wiki](https://github.com/stdevel/satprep/wiki/install#requirements) for more detail information.



Installation and usage
======================
See the [wiki](https://github.com/stdevel/satprep/wiki) for more details about the particular scripts.



Example workflow
================
Create an inventory for all managed hosts, including errata and regular patch information:
```
$ ./satprep_snapshot.py -p
```
Prepare maintenance for affected hosts (*optional*):
```
$ ./satprep_prepare_maintenance.py errata-snapshot*.csv
...
$ ./satprep_prepary_maintenance.py -V errata-snapshot*.csv
```
Patch your systems, reboot them, verify functionality, etc.:

Create another snapshot afterwards:
```
$ ./satprep_snapshot.py -p
```

Create maintenance reports with the information from two snapshot reports:
```
$ ./satprep_diff.py -x errata-diff-report*.csv
```

Or create the same reports with different page orientation, an custom logo (*e.g. company logo*) and a custom footer:
```
$ ./satprep_diff.py -x errata-diff-report* -p potrait -i /opt/tools/myCompany.jpg -f "myCompany maintenance report"
```
