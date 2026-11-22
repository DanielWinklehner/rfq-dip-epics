/* pid.c - the PID algorithm of the MIST-2 loop IOC (see pid.h). Plain C, no EPICS. */
#include "pid.h"

static double clamp(double x, double lo, double hi)
{
    return x < lo ? lo : (x > hi ? hi : x);
}

/* The output limits, then the slew limit from the last output: what the actuator gets.
 * *slewed: the slew limit cut the change. */
static double limit(const pid_state *s, const pid_params *p, double raw, double dt, int *slewed)
{
    double target = clamp(raw, p->out_min, p->out_max);
    double room = p->slew * dt;

    *slewed = 1;
    if (target > s->out + room)
        return s->out + room;
    if (target < s->out - room)
        return s->out - room;
    *slewed = 0;
    return target;
}

void pid_start(pid_state *s, const pid_params *p, double sp, double pv, double out_now)
{
    s->out = out_now;
    s->pv_f = pv;
    s->d_rate = 0.0;
    s->kp = p->kp;
    s->kd = p->kd;
    s->integral = out_now - p->kp * (sp - pv);      /* so that P + I + D = out_now */
    s->limited = PID_FREE;
}

void pid_step(pid_state *s, const pid_params *p, double sp, double pv, double dt, pid_result *r)
{
    double e = sp - pv;
    double pv_f, pterm, dterm, step, wanted, integral, out;
    int slewed;

    if (dt > p->dt_max) {                           /* a long gap: integrate at most dt_max, and */
        dt = p->dt_max;                             /* restart the filter instead of differencing */
        s->pv_f = pv;                               /* over the gap */
        s->d_rate = 0.0;
    }
    if (dt > 0.0) {                                 /* (not for dt <= 0 or not a number) */
        /* A gain change moves the integral by the change of its term: no jump of the output. */
        s->integral += (s->kp - p->kp) * e + (p->kd - s->kd) * s->d_rate;
        s->kp = p->kp;
        s->kd = p->kd;

        /* Derivative of the measurement through a first-order filter (backward Euler: stable
         * for every dt and tf). */
        pv_f = s->pv_f + (pv - s->pv_f) * dt / ((p->tf > 0.0 ? p->tf : 0.0) + dt);
        s->d_rate = (pv_f - s->pv_f) / dt;
        s->pv_f = pv_f;

        /* Integrate, but only as far as the output stays within its limits. */
        pterm = p->kp * e;
        dterm = -p->kd * s->d_rate;
        step = p->ki * e * dt;
        wanted = pterm + s->integral + step + dterm;
        integral = s->integral + step;
        if (step > 0.0 && wanted > p->out_max)
            integral = s->integral > p->out_max - pterm - dterm ? s->integral : p->out_max - pterm - dterm;
        if (step < 0.0 && wanted < p->out_min)
            integral = s->integral < p->out_min - pterm - dterm ? s->integral : p->out_min - pterm - dterm;
        integral = clamp(integral, p->out_min, p->out_max);
        out = limit(s, p, pterm + integral + dterm, dt, &slewed);
        /* ... and not at all while the slew limit holds the output back in its direction. */
        if (slewed && (out - s->out) * step > 0.0) {
            integral = clamp(s->integral, p->out_min, p->out_max);
            out = limit(s, p, pterm + integral + dterm, dt, &slewed);
        }
        s->integral = integral;
        s->out = out;
        s->limited = slewed ? PID_AT_SLEW
                   : (wanted > p->out_max && out >= p->out_max) ? PID_AT_MAX
                   : (wanted < p->out_min && out <= p->out_min) ? PID_AT_MIN : PID_FREE;
    }

    r->out = s->out;
    r->error = e;
    r->p = s->kp * e;
    r->i = s->integral;
    r->d = -s->kd * s->d_rate;
    r->limited = s->limited;
}
