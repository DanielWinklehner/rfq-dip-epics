import logging

# The scan logs every end as a warning; the tests check the files, not the log.
logging.getLogger("mist2scan").addHandler(logging.NullHandler())
logging.getLogger("mist2scan").propagate = False
