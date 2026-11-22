TOP=../..

include $(TOP)/configure/CONFIG
#----------------------------------------
#  ADD MACRO DEFINITIONS AFTER THIS LINE
#=============================

PROD_IOC = mist2

# mist2.dbd is made from these
DBD += mist2.dbd
mist2_DBD += base.dbd
mist2_DBD += asyn.dbd
mist2_DBD += drvAsynIPPort.dbd
mist2_DBD += drvAsynSerialPort.dbd
mist2_DBD += stream.dbd
mist2_DBD += asSupport.dbd
mist2_DBD += pidLoop.dbd

mist2_SRCS += mist2_registerRecordDeviceDriver.cpp
mist2_SRCS_DEFAULT += mist2Main.cpp

# The PID loop (EPICS/Db/loop.db): the algorithm in plain C (pid.c, tested alone by pidTest.mk)
# and the subroutine of its aSub record (pidLoop.c)
mist2_SRCS += pid.c
mist2_SRCS += pidLoop.c

mist2_LIBS += autosave
mist2_LIBS += stream
mist2_LIBS += asyn
mist2_LIBS += $(EPICS_BASE_IOC_LIBS)

# asyn links libtirpc on Linux when it was built with TIRPC=YES
mist2_SYS_LIBS_Linux += tirpc

#===========================

include $(TOP)/configure/RULES
#----------------------------------------
#  ADD RULES AFTER THIS LINE
