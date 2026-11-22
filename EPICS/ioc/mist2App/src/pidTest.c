/* pidTest.c - the PID algorithm (pid.c) alone, without EPICS and without the emulation.
 *
 *   make -f pidTest.mk -C EPICS/ioc/mist2App/src        (from the repository root)
 *
 * Prints one line per check and exits with 1 if any check fails.
 */
#include <math.h>
#include <stdio.h>

#include "pid.h"

static int failures, checks;

static void check(int ok, const char *what, double got, double want)
{
    checks++;
    if (!ok)
        failures++;
    printf("%s  %-62s got %.6g, want %.6g\n", ok ? "PASS" : "FAIL", what, got, want);
}

static void near(const char *what, double got, double want, double tol)
{
    check(fabs(got - want) <= tol, what, got, want);
}

/* Parameters without limits that matter: wide output range, fast slew, no derivative filter. */
static pid_params wide(double kp, double ki, double kd)
{
    pid_params p = {kp, ki, kd, 0.0, -1e6, 1e6, 1e6, 1.0};
    return p;
}

static void terms(void)
{
    pid_state s;
    pid_result r;
    pid_params p = wide(2.0, 0.0, 0.0);
    int k;

    puts("== each term");
    pid_start(&s, &p, 5.0, 5.0, 10.0);
    pid_step(&s, &p, 5.0, 4.0, 0.1, &r);
    near("P: e = 1, Kp = 2 -> p = 2", r.p, 2.0, 1e-12);
    near("P: output = start + Kp e", r.out, 12.0, 1e-12);

    p = wide(0.0, 0.5, 0.0);
    pid_start(&s, &p, 5.0, 5.0, 10.0);
    for (k = 0; k < 10; k++)
        pid_step(&s, &p, 5.0, 4.0, 0.1, &r);
    near("I: Ki = 0.5, e = 1 for 1 s -> I grows by 0.5", r.i, 10.5, 1e-9);
    near("I: output follows I", r.out, 10.5, 1e-9);

    p = wide(0.0, 0.0, 1.0);
    pid_start(&s, &p, 5.0, 0.0, 10.0);
    for (k = 1; k <= 5; k++)
        pid_step(&s, &p, 5.0, 0.1 * k, 0.1, &r);
    near("D: measurement rises 1 per s, Kd = 1 -> d = -1", r.d, -1.0, 1e-9);
    pid_step(&s, &p, 9.0, 0.6, 0.1, &r);
    near("D: a set point step does not reach the derivative", r.d, -1.0, 1e-9);

    p = wide(0.0, 0.0, 1.0);
    p.tf = 1.0;
    pid_start(&s, &p, 0.0, 0.0, 0.0);
    pid_step(&s, &p, 0.0, 1.0, 0.1, &r);
    near("D filter: step 1, tf 1 s, dt 0.1 s -> d = -(0.1/1.1)/0.1", r.d, -1.0 / 1.1, 1e-9);
}

static void limits(void)
{
    pid_state s;
    pid_result r;
    pid_params p = wide(10.0, 0.0, 0.0);
    int k;

    puts("== output limits and slew limit");
    p.out_min = 0.0;
    p.out_max = 20.0;
    pid_start(&s, &p, 0.0, 0.0, 10.0);
    pid_step(&s, &p, 5.0, 0.0, 0.1, &r);
    near("maximum: raw 60 -> output 20", r.out, 20.0, 1e-12);
    check(r.limited == PID_AT_MAX, "maximum: flag at maximum", r.limited, PID_AT_MAX);
    pid_step(&s, &p, -5.0, 0.0, 0.1, &r);
    near("minimum: raw -40 -> output 0", r.out, 0.0, 1e-12);
    check(r.limited == PID_AT_MIN, "minimum: flag at minimum", r.limited, PID_AT_MIN);
    pid_step(&s, &p, 0.5, 0.0, 0.1, &r);
    check(r.limited == PID_FREE, "inside the limits: no flag", r.limited, PID_FREE);

    p = wide(10.0, 0.0, 0.0);
    p.slew = 2.0;
    pid_start(&s, &p, 0.0, 0.0, 10.0);
    pid_step(&s, &p, 1.0, 0.0, 0.1, &r);
    near("slew: 2 per s, dt 0.1 s -> the output moves 0.2", r.out, 10.2, 1e-12);
    check(r.limited == PID_AT_SLEW, "slew: flag slew", r.limited, PID_AT_SLEW);
    for (k = 0; k < 100; k++)
        pid_step(&s, &p, 1.0, 0.0, 0.1, &r);
    near("slew: then it reaches the target of 20", r.out, 20.0, 1e-9);
    check(r.limited == PID_FREE, "slew: and the flag goes", r.limited, PID_FREE);

    p.out_max = 15.0;
    pid_step(&s, &p, 1.0, 0.0, 0.1, &r);
    near("maximum lowered under the output: it moves down at the slew rate", r.out, 19.8, 1e-9);
}

/* Output at the maximum for a long time with the error pushing up, then the error reverses. */
static void antiwindup(void)
{
    pid_state s;
    pid_result r;
    pid_params p = wide(1.0, 1.0, 0.0);
    int k;

    puts("== anti-windup");
    p.out_min = 0.0;
    p.out_max = 20.0;
    pid_start(&s, &p, 10.0, 10.0, 10.0);
    for (k = 0; k < 1000; k++)                      /* 100 s with e = +3: at the limit after 2.3 s */
        pid_step(&s, &p, 13.0, 10.0, 0.1, &r);
    near("after 100 s with e = +3 the output is at the maximum", r.out, 20.0, 1e-12);
    check(r.limited == PID_AT_MAX, "and flagged at maximum", r.limited, PID_AT_MAX);
    near("the integral stopped where the output reached the limit", r.i, 17.0, 1e-9);
    pid_step(&s, &p, 9.5, 10.0, 0.1, &r);           /* e = -0.5 */
    check(r.out < 20.0, "first step with e < 0: the output leaves the maximum", r.out, 20.0);
    near("first step with e < 0: by Kp de + Ki e dt", r.out, 17.0 - 0.5 - 0.05, 1e-9);

    pid_start(&s, &p, 10.0, 10.0, 18.0);            /* the maximum lowered under the integral */
    p.out_max = 15.0;
    for (k = 0; k < 100; k++)
        pid_step(&s, &p, 10.0, 10.0, 0.1, &r);
    near("maximum lowered from 20 to 15 at e = 0: the output follows it", r.out, 15.0, 1e-12);
    pid_step(&s, &p, 9.5, 10.0, 0.1, &r);
    check(r.out < 15.0, "and leaves it at the first step with e < 0", r.out, 15.0);
    p.out_max = 20.0;

    p.slew = 0.1;                                   /* the same against the slew limit */
    pid_start(&s, &p, 10.0, 10.0, 10.0);
    for (k = 0; k < 100; k++)
        pid_step(&s, &p, 13.0, 10.0, 0.1, &r);
    check(r.limited == PID_AT_SLEW, "slow slew: the output is slew limited", r.limited, PID_AT_SLEW);
    near("slow slew: it rose by slew x 10 s", r.out, 11.0, 1e-9);
    near("slow slew: the integral did not grow meanwhile", r.i, 10.0, 1e-9);
}

static void bumpless(void)
{
    pid_state s;
    pid_result r;
    pid_params p = wide(2.0, 0.5, 1.0);
    double before;

    puts("== bumpless start and parameter changes");
    pid_start(&s, &p, 20.0, 18.0, 88.0);            /* e = 2: Kp e = 4 */
    pid_step(&s, &p, 20.0, 18.0, 0.0, &r);
    near("start: the first output is the actuator's present value", r.out, 88.0, 1e-12);
    pid_step(&s, &p, 20.0, 18.0, 0.1, &r);
    near("start: the next one differs only by Ki e dt", r.out, 88.0 + 0.5 * 2.0 * 0.1, 1e-12);

    before = r.out;
    p.kp = 6.0;
    pid_step(&s, &p, 20.0, 18.0, 0.1, &r);
    near("Kp 2 -> 6 with e = 2: no jump (only Ki e dt)", r.out - before, 0.1, 1e-12);

    pid_start(&s, &p, 20.0, 18.0, 88.0);
    pid_step(&s, &p, 20.0, 18.1, 0.1, &r);          /* measurement rising: d_rate = 1 */
    before = r.out;
    p.kd = 3.0;
    pid_step(&s, &p, 20.0, 18.2, 0.1, &r);
    near("Kd 1 -> 3 while the measurement rises: no jump of the D term",
         r.out - before, 6.0 * -0.1 + 0.5 * 1.8 * 0.1, 1e-9);

    before = r.out;
    p.ki = 5.0;
    pid_step(&s, &p, 20.0, 18.3, 0.1, &r);
    near("Ki 0.5 -> 5: no jump (I is the sum of Ki e dt)", r.out - before,
         6.0 * -0.1 + 5.0 * 1.7 * 0.1, 1e-9);

    p = wide(2.0, 0.0, 0.0);
    p.slew = 1.0;
    pid_start(&s, &p, 20.0, 20.0, 88.0);
    pid_step(&s, &p, 22.0, 20.0, 0.1, &r);
    near("set point +2 with Kp 2: the P step of 4 is cut to slew x dt", r.out, 88.1, 1e-12);
}

static void dt_guards(void)
{
    pid_state s, copy;
    pid_result r;
    pid_params p = wide(1.0, 1.0, 1.0);

    puts("== dt guards");
    pid_start(&s, &p, 10.0, 9.0, 50.0);
    pid_step(&s, &p, 10.0, 9.0, 0.1, &r);
    copy = s;
    pid_step(&s, &p, 10.0, 5.0, 0.0, &r);
    near("dt = 0: the output stays", r.out, copy.out, 0.0);
    check(s.integral == copy.integral && s.pv_f == copy.pv_f, "dt = 0: the state stays",
          s.integral, copy.integral);
    pid_step(&s, &p, 10.0, 5.0, -1.0, &r);
    near("dt < 0: the output stays", r.out, copy.out, 0.0);
    pid_step(&s, &p, 10.0, 5.0, NAN, &r);
    near("dt not a number: the output stays", r.out, copy.out, 0.0);
    check(s.integral == copy.integral, "dt not a number: the integral stays", s.integral, copy.integral);

    pid_step(&s, &p, 10.0, 9.0, 1000.0, &r);        /* dt_max = 1 s */
    near("dt 1000 s: integrated as dt_max (1 s)", r.i, copy.integral + 1.0, 1e-12);
    near("dt 1000 s: the derivative starts again (no kick)", r.d, 0.0, 0.0);
}

int main(void)
{
    terms();
    limits();
    antiwindup();
    bumpless();
    dt_guards();
    printf("\npidTest: %d checks, %d failed\n", checks, failures);
    return failures ? 1 : 0;
}
