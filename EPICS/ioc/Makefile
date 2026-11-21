# Makefile at the top of the MIST-2 IOC application
TOP = .
include $(TOP)/configure/CONFIG

DIRS += configure
DIRS += mist2App
mist2App_DEPEND_DIRS = configure

# iocBoot holds only startup files, nothing is built there (no envPaths, see iocBoot/run-ioc.sh)

include $(TOP)/configure/RULES_TOP
