/* pidLoop.c - record glue of a PID loop: the subroutine of the aSub record of EPICS/Db/loop.db.
 *
 * The algorithm is pid.c. This file decides, once per scan of the aSub record, whether the loop
 * runs (PID) or follows the actuator (MANUAL), hands back to MANUAL when a condition fails,
 * refuses a request for PID while one fails, and says when the actuator is written.
 * It knows no PV name: every input comes from a record of the same loop.db through a database
 * link (the remote PVs are read by the mirror records of loop.db, whose severity says whether
 * their source is valid and connected).
 *
 * Inputs (fields A to U of the aSub record, see loop.db):
 *   A mode request (0 MANUAL, 1 PID)   B set point     C, D its limits (DRVL, DRVH)
 *   E measurement   F its severity     G actuator's set point   H its severity
 *   I heartbeat of the IOC that owns the measurement
 *   J, K, L permit conditions 1 to 3: 0 fulfilled, 1 not fulfilled, 2 no data
 *   M Kp  N Ki  O Kd  P derivative filter time  Q output minimum  R output maximum
 *   S slew per second  T stale time  U resolution of the actuator
 * Outputs:
 *   VALA mode   VALB mode request (written back: MANUAL after a hand-back or refusal)
 *   VALC reason   VALD limit flag   VALE output   VALF error   VALG, VALH, VALI the P, I, D terms
 *   VALJ value to write to the actuator   VALK 1: write it now
 */
#include <math.h>
#include <stdlib.h>

#include <aSubRecord.h>
#include <alarm.h>
#include <dbScan.h>
#include <epicsExport.h>
#include <epicsTime.h>
#include <errlog.h>
#include <registryFunction.h>

#include "pid.h"

/* The reasons, in the order of the states of $(P):reason:get in loop.db. */
enum {
    R_NONE, R_START, R_PERMIT1, R_PERMIT2, R_PERMIT3, R_NODATA1, R_NODATA2, R_NODATA3,
    R_MEASUREMENT, R_ACTUATOR, R_STALE, R_OVERRIDDEN, R_NOT_ACCEPTED, R_RANGE
};

#define DT_MAX_PERIODS 3.0      /* a gap longer than three scan periods is integrated as three */

typedef struct {
    int started;                /* the first run after the IOC start is done */
    int pid;                    /* mode: 0 MANUAL, 1 PID */
    int reason;
    double dt_max;
    epicsUInt64 last_run;       /* monotonic clock, ns */
    double hb;                  /* heartbeat value seen last, and when it last changed */
    int hb_changed;
    epicsUInt64 hb_time;
    double written, written_before;   /* the last two values the loop sent to the actuator */
    pid_state state;
    pid_result r;
} loop_t;

#define IN(field) (*(double *)prec->field)
#define OUT(field) (*(double *)prec->field)

static long pidLoopInit(aSubRecord *prec)
{
    loop_t *L = calloc(1, sizeof(loop_t));

    if (!L)
        return -1;
    L->reason = R_START;
    prec->dpvt = L;
    return 0;
}

static int same(double a, double b)
{
    return fabs(a - b) <= 1e-9 * (fabs(a) + fabs(b) + 1.0);
}

/* The first condition that is not fulfilled, or R_NONE. In PID an INVALID set point of the
 * actuator means the actuator did not accept the loop's set (the loop is the writer then). */
static int check(const loop_t *L, aSubRecord *prec, int in_pid, int stale)
{
    double c[3] = {IN(j), IN(k), IN(l)};
    int n;

    if (IN(f) >= INVALID_ALARM)
        return R_MEASUREMENT;
    if (IN(h) >= INVALID_ALARM)
        return in_pid ? R_NOT_ACCEPTED : R_ACTUATOR;
    for (n = 0; n < 3; n++)
        if (c[n] > 1.5)
            return R_NODATA1 + n;
    for (n = 0; n < 3; n++)
        if (c[n] > 0.5)
            return R_PERMIT1 + n;
    if (stale)
        return R_STALE;
    if (in_pid && !same(IN(g), L->written) && !same(IN(g), L->written_before))
        return R_OVERRIDDEN;
    if (!in_pid && !(IN(q) < IN(r) && IN(g) >= IN(q) && IN(g) <= IN(r)))
        return R_RANGE;
    return R_NONE;
}

static long pidLoopProcess(aSubRecord *prec)
{
    loop_t *L = prec->dpvt;
    epicsUInt64 now = epicsMonotonicGet();
    double sp = IN(b), pv = IN(e), act = IN(g);
    int request = IN(a) > 0.5;
    int stale, why, write = 0;
    double dt;
    pid_params p;

    if (!L)
        return -1;
    dt = L->last_run ? (now - L->last_run) * 1e-9 : 0.0;
    L->last_run = now;
    if (IN(d) > IN(c))
        sp = sp < IN(c) ? IN(c) : (sp > IN(d) ? IN(d) : sp);

    /* Stale: the heartbeat has not changed for longer than the stale time (or never). */
    if (L->started && IN(i) != L->hb) {
        L->hb_changed = 1;
        L->hb_time = now;
    }
    L->hb = IN(i);
    stale = !L->hb_changed || (now - L->hb_time) * 1e-9 > IN(t);

    if (!L->started)                        /* scan periods are known from the first scan on */
        L->dt_max = DT_MAX_PERIODS * scanPeriod(prec->scan);
    p.dt_max = L->dt_max;
    p.kp = IN(m);
    p.ki = IN(n);
    p.kd = IN(o);
    p.tf = IN(p);
    p.out_min = IN(q);
    p.out_max = IN(r);
    p.slew = IN(s);

    if (!L->started) {                      /* IOC start: always MANUAL */
        L->started = 1;
        request = 0;
        if (!(L->dt_max > 0.0))
            errlogPrintf("%s: the loop needs a periodic SCAN, it stays in MANUAL\n", prec->name);
    } else if (!L->pid) {
        if (request && L->dt_max > 0.0) {
            why = check(L, prec, 0, stale);
            if (why) {                      /* refused */
                L->reason = why;
                request = 0;
            } else {                        /* MANUAL -> PID: the first output is act */
                L->pid = 1;
                L->reason = R_NONE;
                L->written = L->written_before = act;
                pid_start(&L->state, &p, sp, pv, act);
                pid_step(&L->state, &p, sp, pv, 0.0, &L->r);
            }
        }
    } else if (!request) {                  /* the operator switched to MANUAL */
        L->pid = 0;
        L->reason = R_NONE;
    } else if ((why = check(L, prec, 1, stale))) {
        L->pid = 0;                         /* hand-back: the actuator keeps its set point */
        L->reason = why;
        request = 0;
    } else {
        pid_step(&L->state, &p, sp, pv, dt, &L->r);
        if (fabs(L->r.out - L->written) >= IN(u)) {
            write = 1;
            L->written_before = L->written;
            L->written = L->r.out;
        }
    }

    if (!L->pid) {                          /* MANUAL: follow the actuator, no terms */
        L->r.out = act;
        L->r.error = sp - pv;
        L->r.p = L->r.i = L->r.d = 0.0;
        L->r.limited = PID_FREE;
    }
    OUT(vala) = L->pid;
    OUT(valb) = request;
    OUT(valc) = L->reason;
    OUT(vald) = L->r.limited;
    OUT(vale) = L->r.out;
    OUT(valf) = L->r.error;
    OUT(valg) = L->r.p;
    OUT(valh) = L->r.i;
    OUT(vali) = L->r.d;
    OUT(valj) = L->written;
    OUT(valk) = write;
    return 0;
}

epicsRegisterFunction(pidLoopInit);
epicsRegisterFunction(pidLoopProcess);
