/**
 * millis.h
 *
 * Tested Compatbility:
 * - Windows (MSVC / mingw)
 * - Linux (gcc)
 *
 * This file provides supplementary functions for obtaining the number of
 * milliseconds since the epoch. However this value may overflow (as a
 * 32-bit long), so use only for comparisons of time. Similar to Arduino's
 * millis() functionality. In addition, provides functions to call OS
 * scheduler sleep functions.
 *
 * Author(s): Ryan Yang (ryang2@mit.edu)
 * Changlog:
 * 2021/05/23 - Documentation
 * 2021/05/17 - Added millis.h
 *
 * References:
 * - https://stackoverflow.com/a/26085827
 * - https://stackoverflow.com/a/28827188
 */

#include <stdint.h>

#if defined(_WIN32) || defined(WIN32)
    #include <Windows.h>
#else
    #include <sys/time.h> // for gettimeofday
    #if _POSIX_C_SOURCE >= 199309L
        #include <time.h>   // for nanosleep
    #else
        #include <unistd.h> // for usleep
    #endif
#endif

#if defined(_WIN32) || defined(WIN32)
static int gettimeofday(struct timeval* tp, struct timezone* tzp) {
    // Note: some broken versions only have 8 trailing zero's, the correct epoch has 9 trailing zero's
    // This magic number is the number of 100 nanosecond intervals since January 1, 1601 (UTC)
    // until 00:00:00 January 1, 1970 
    static const uint64_t EPOCH = ((uint64_t) 116444736000000000ULL);

    SYSTEMTIME  system_time;
    FILETIME    file_time;
    uint64_t    time;

    GetSystemTime( &system_time );
    SystemTimeToFileTime( &system_time, &file_time );
    time =  ((uint64_t)file_time.dwLowDateTime )      ;
    time += ((uint64_t)file_time.dwHighDateTime) << 32;

    tp->tv_sec  = (long) ((time - EPOCH) / 10000000L);
    tp->tv_usec = (long) (system_time.wMilliseconds * 1000);
    return 0;
}
#endif

static unsigned long millis(void) {
    struct timeval now;
    gettimeofday(&now, NULL);
    return (now.tv_sec * 1000) + (unsigned long)(now.tv_usec/1000.0f);
}

static void sleep_ms(int milliseconds){ // cross-platform sleep function
#if defined(_WIN32) || defined(WIN32)
    Sleep(milliseconds);
#elif _POSIX_C_SOURCE >= 199309L
    struct timespec ts;
    ts.tv_sec = milliseconds / 1000;
    ts.tv_nsec = (milliseconds % 1000) * 1000000;
    nanosleep(&ts, NULL);
#else
    if (milliseconds >= 1000)
      sleep(milliseconds / 1000);
    usleep((milliseconds % 1000) * 1000);
#endif
}

