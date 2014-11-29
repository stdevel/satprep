satprep
=======

**satprep** is a Python toolkit for generating CSV/PDF patch reports for systems managed with [Spacewalk](http://www.spacewalkproject.org/), [Red Hat Satellite](http://www.redhat.com/products/enterprise-linux/satellite/) or [SUSE Manager](http://www.suse.com/products/suse-manager/).
 
This can be very useful if you need to document software changes due to IT certifications like [ISO/IEC 27001:2005](http://en.wikipedia.org/wiki/ISO/IEC_27001:2005) or many other.

After doing maintenance tasks this toolkit can create detailed change reports per host. Before rebooting patched systems you can also automate scheduling downtime for your systems monitored by [Nagios](http://www.nagios.org/), [Icinga](http://www.icinga.org/), [Thruk](http://www.thruk.org/) and [Shinken](http://www.shinken-monitoring.org).



What does it look like?
=======================

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
4. `satprep_schedule_downtime.py` - schedules downtimes for affected systems monitored by Nagios, Icinga, Thruk or Shinken
3. `satprep_diff.py` - creates the delta, required to create the maintenance reports
 


Make sure to follow this procedure to document your maintenance tasks:

1. do a complete patch/errata inventory of your landscape: `./satprep_snapshot.py`
2. notice that a CSV report was created: `errata-snapshot-report-$RHNhostname-YYYYMMDD-HHMM.csv`
3. complete your system maintenance tasks (*create virtual machine snapshots, patch and reboot systems, etc.*), run `./satprep_schedule_downtime.py` in case your systems are monitored with Nagios, Icinga, Thruk or Shinken
4. do another complete patch/errata inventory: `./satprep_snapshot.py`
5. create a difference report and host reports: `./satprep_diff.py *.csv`

Afterwards the reports are stored in `/tmp`.

For gathering optional semantic information (*e.g. backup and monitoring*) the script makes usage of the **custom system information** feature of Spacewalk, Red Hat Satellite or SUSE Manager. After installing the custom keys using the `satprep_install_custominfo.py` utility you can assign the following information per host (*only a selection*):
* **SYSTEM_OWNER** - server responsible in your team
* **SYSTEM_MONITORING** - monitoring state (*0 or empty = disabled, 1 = enabled*))
* **SYSTEM_BACKUP** - defines whether the host is protected using backups (*0 or empty = no, 1 = yes*)
* **SYSTEM_ANTIVIR** - defines whether the host is protected against viruses (*0 or empty = no, 1 = yes*)

See the [wiki](https://github.com/stdevel/satprep/wiki) for more details about the particular scripts.


Requirements
============

**satprep** needs Python 2.6 or newer - it runs on EL5/6 machines without adding additional software repositories (*that's by the way one reason why I had chosen optparse instead of argparse*).
The following Python modules are used:
* optparse
* sys
* os
* stat
* difflib
* time
* csv
* string
* datetime
* time
* getpass
* xmlrpclic (*shipped with `rhnlib`*)
* pprint
* logging
* requests

The toolkit needs the `pdflatex` binary which is usually part of the LaTeX or TeX Live software set provided by your distributor (*for EL you’ll need the `texlive-latex`package*). You need to install one of both.
The template which is used by **satprep** uses the following LaTeX modules:
* wasysym
* tabularx
* colortbl
* array
* hyper
* graphicx

Usually these modules should already be part of your LaTeX or TeX Live distribution.



Usage
=====

See the [wiki](https://github.com/stdevel/satprep/wiki) for more details about the particular scripts.



Example workflow
================

Create an inventory for all managed hosts, including errata and regular patch information:
```
$ ./satprep_snapshot.py -p
```
Schedule downtime for affected hosts (*optional*):
```
$ ./satprep_schedule_downtime.py -u admin -p password errata-snapshot-report-localhost-20140728-23*.csv
```
Patch your systems, reboot them, verify functionality, etc.:

Create another snapshot afterwards:
```
$ ./satprep_snapshot.py -p
```

Create maintenance reports with the information from two snapshot reports:
```
$ ./satprep_diff.py -x errata-snapshot-report-localhost-20140728-23*.csv
```

Or create the same reports with different page orientation, an custom logo (*e.g. company logo*) and a custom footer:
```
$ ./satprep_diff.py -x errata-snapshot-report-localhost-20140728-23* -p potrait -i /opt/tools/myCompany.jpg -f "myCompany maintenance report"
```
