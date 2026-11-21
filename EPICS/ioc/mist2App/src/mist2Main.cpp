/* mist2Main.cpp - main program of the MIST-2 IOC
 *
 * Runs the startup script given as argument, then:
 * - stdin is a terminal (docker attach, a console): the interactive IOC shell. "exit" stops the IOC.
 * - stdin is not a terminal (a container without tty, a service manager): no shell, the IOC runs
 *   until it gets a signal. Without this the IOC would read end-of-file and exit at once.
 * A startup script that fails (iocsh returns non-zero, see "on error halt" in st.cmd) stops the
 * IOC with exit code 1, so that it never runs half configured.
 */
#include <stdio.h>
#include <unistd.h>

#include "epicsExit.h"
#include "epicsThread.h"
#include "iocsh.h"

int main(int argc, char *argv[])
{
    int interactive = isatty(STDIN_FILENO);

    /* Line-buffered output, so that docker logs and log files show lines as they come. */
    setvbuf(stdout, NULL, _IOLBF, BUFSIZ);

    if (argc >= 2) {
        if (iocsh(argv[1]) != 0) {
            fprintf(stderr, "mist2: startup script %s failed, IOC stops\n", argv[1]);
            epicsExit(1);
        }
        epicsThreadSleep(.2);
    }
    if (interactive) {
        iocsh(NULL);
    } else {
        printf("mist2: stdin is not a terminal, running without interactive shell\n");
        for (;;)
            epicsThreadSleep(3600.0);
    }
    epicsExit(0);
    return 0;
}
