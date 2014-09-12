#! /usr/bin/env python
# -*- coding: utf-8 -*-
import getpass
import logging
import os
import stat
import sys

LOGGER = LOGGER = logging.getLogger('satprep-shared')


SUPPORTED_API_LEVELS = ["11.1", "12", "13", "13.0", "14", "14.0", "15", "15.0"]


def get_credentials(input_file=None):
    if input_file:
        LOGGER.debug("DEBUG: using authfile")
        try:
            # check filemode and read file
            filemode = oct(stat.S_IMODE(os.lstat(input_file).st_mode))
            if filemode == "0600":
                LOGGER.debug("DEBUG: file permission matches 0600")
                with open(input_file, "r") as auth_file:
                    s_username = auth_file.readline()
                    s_password = auth_file.readline()
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
