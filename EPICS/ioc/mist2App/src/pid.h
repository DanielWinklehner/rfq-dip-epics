/* pid.h - the PID algorithm of the MIST-2 loop IOC. Plain C, no EPICS: pidTest.c tests it alone.
 *
 *   u = Kp*e + I - Kd*d(pv_f)/dt        e = sp - pv        I += Ki*e*dt
 *
 * Parallel form. The derivative acts on the filtered measurement pv_f, not on the error, so a set
 * point step does not kick the output. The output is limited to [out_min, out_max] and its rate
 * to slew per second, in this order; what pid_step returns is what goes to the actuator.
 *
 * Anti-windup: conditional integration. The integral takes the step Ki*e*dt only as far as the
 * output stays within [out_min, out_max], and not at all while the slew limit holds the output
 * back in the direction of the step. The integral itself stays within [out_min, out_max]. So
 * after a long time at a limit the output leaves it as soon as the error changes sign.
 *
 * Bumpless: pid_start sets the integral so that the output equals the actuator's present value.
 * A change of Kp or Kd moves the integral by the change of its term, so that the output does not
 * jump. A change of the set point moves the output by Kp times the change, a change of a limit
 * moves it towards the new limit; both through the slew limit.
 */
#ifndef MIST2_PID_H
#define MIST2_PID_H

typedef struct {
    double kp;          /* output units per measurement unit */
    double ki;          /* output units per measurement unit and second */
    double kd;          /* output units per (measurement unit per second) */
    double tf;          /* time constant of the derivative's filter, s; 0: no filter */
    double out_min;     /* output limits, output units */
    double out_max;
    double slew;        /* largest change of the output, output units per second */
    double dt_max;      /* longest time step that is integrated, s */
} pid_params;

typedef struct {
    double out;         /* last output */
    double integral;    /* the I term, output units */
    double pv_f;        /* filtered measurement */
    double d_rate;      /* d(pv_f)/dt of the last step */
    double kp, kd;      /* gains of the last step: a change is compensated in the integral */
    int limited;        /* which limit held the last output back (PID_FREE, ...) */
} pid_state;

enum { PID_FREE = 0, PID_AT_MIN = 1, PID_AT_MAX = 2, PID_AT_SLEW = 3 };

typedef struct {
    double out;         /* the output: what the actuator is to be set to */
    double error;       /* sp - pv */
    double p, i, d;     /* the three terms; p + i + d is the output before the limits */
    int limited;        /* PID_FREE, or which limit holds the output back */
} pid_result;

/* Start from the actuator's present value `out_now`. A pid_step with dt = 0 then returns it as
 * the first output; the steps after it continue from there. */
void pid_start(pid_state *s, const pid_params *p, double sp, double pv, double out_now);

/* One step after dt seconds. dt <= 0 (or not a number): nothing changes, the last output is
 * returned. dt longer than dt_max: integrated as dt_max, and the derivative's filter starts
 * again from pv. */
void pid_step(pid_state *s, const pid_params *p, double sp, double pv, double dt, pid_result *r);

#endif
