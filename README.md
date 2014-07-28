satprep
=======

**satprep** is a Python toolkit for generating CSV/PDF patch reports for systems managed with Spacewalk, Red Hat Satellite or SUSE Manager.
 
This can be very useful if you need to document software changes due to IT certifications like [ISO/IEC 27001:2005](http://en.wikipedia.org/wiki/ISO/IEC_27001:2005) or many other.
 
After doing maintenance tasks this toolkit can create detailed change reports per host.



What does it look like?
=======================

A maintenance report looks like this:
![Example satprep maintenance report](https://raw.githubusercontent.com/stdevel/satprep/master/satprep_example_report.png "Example satprep maintenance report")



How does it work?
=================

The toolkit consists of three scripts:


1. `satprep_install_custominfo.py` - installs necessary custom information (*see above*) for your hosts managed with Spacewalk, Red Hat Satellite or SUSE Manager. You will need to execute this script once to make sure that all information can be assigned
2. `satprep_snapshot.py` - creates an inventory of the current available patches and errata to your system landscape. It gathers the following information:
  * system hostname and IP
  * system virtualization guest status
  * system owner / cluster member / monitoring / backup / anti-virus status (*optional*)
  * errata information including name, date, description, advisory type (*security/bugfix/enhancement update*) and even whether a reboot is required
  * also regular patch information (*optional*)
3. `satprep_diff.py` - creates the delta, required to create the maintenance reports
 


Make sure to follow this procedure to document your maintenance tasks:

1. do a complete patch/errata inventory of your landscape: `./satprep_snapshot.py`
2. notice that a CSV report was created: `errata-snapshot-report-$RHNhostname-YYYYMMDD-HHMM.csv`
3. complete your system maintenance tasks (*create virtual machine snapshots, patch and reboot systems, etc.*)
4. do another complete patch/errata inventory: `./satprep_snapshot.py`
5. create a difference report and host reports: `./satprep_diff.py *.csv`

Afterwards the reports are stored in `/tmp`.

For gathering optional semantic information (*e.g. backup and monitoring*) the script makes usage of the **custom system information** feature of Spacewalk, Red Hat Satellite or SUSE Manager. After installing the custom keys using the `satprep_install_custominfo.py` utility you can assign the following information per host:
* **SYSTEM_OWNER** - server responsible in your team
* **SYSTEM_CLUSTER** - defines whether the host is a cluster system
* **SYSTEM_MONITORING** - monitoring state (*0 = disabled, 1 = enabled*)
* **SYSTEM_MONITORING_NOTES** - notes explaining why the monitoring is unavailable (*e.g. test system*)
* **SYSTEM_BACKUP** - defines whether the host is protected using backups
* **SYSTEM_BACKUP_NOTES** - notes explaining why backup is not configured (*e.g. development system*)
* **SYSTEM_ANTIVIR** - defines whether the host is protected against viruses
* **SYSTEM_ANTIVIR_NOTES** - explanation why anti-virus is not configured (*e.g. no concept*)



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

The appropriate tools have plenty of command line options to customize your reports:
```
$ ./satprep_snapshot.py -f FOOBAR
Usage: satprep_snapshot.py [options]

satprep_snapshot.py: error: option -f: invalid choice: 'FOOBAR' (choose from 'hostname', 'ip', 'errata_name', 'errata_type', 'errata_desc', 'errata_date', 'errata_reboot', 'system_owner', 'system_cluster', 'system_virt', 'system_monitoring', 'system_monitoring_notes', 'system_backup', 'system_backup_notes', 'system_antivir', 'system_antivir_notes')
```

```
$ ./satprep_diff.py -h
…

Options:
  --version             show program's version number and exit
  -h, --help            show this help message and exit
  -q, --quiet           don't print status messages to stdout
  -d, --debug           enable debugging outputs
  -t FILE, --template=FILE
                        defines the template which is used to generate the
                        report
  -o FILE, --output=FILE
                        define report filename. (default: errata-diff-report-
                        Ymd.csv)
  -n, --no-host-reports
                        only create delta CSV report and skip creating host
                        reports
  -x, --preserve-tex    keeps the TeX files after creating the PDF reports
                        (default: no)
  -p [landscape|potrait], --page-orientation=[landscape|potrait]
                        defines the orientation of the PDF report (default:
                        landscape)
  -i FILE, --image=FILE
                        defines a different company logo
  -f STRING, --footer=STRING
                        changes footer text
  -b PATH, --pdflatex-binary=PATH
                        location for the pdflatex binary
```



Examples
========

Create an inventory for all managed hosts, including errata and regular patch information
```
$ ./satprep_snapshot.py -p
```

Create maintenance reports with the information from two snapshot reports:
```
$ ./satprep_diff.py -x errata-snapshot-report-localhost-20140728-23*
```

Create the same reports with different page orientation, an custom logo (*e.g. company logo*) and a custom footer:
```
$ ./satprep_diff.py -x errata-snapshot-report-localhost-20140728-23* -p potrait -i /opt/tools/myCompany.jpg -f “myCompany maintenance report“
```
