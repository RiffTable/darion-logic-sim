/*
 * vpi_timer.c — VPI wall-clock timer for Icarus Verilog benchmarking
 * =====================================================================
 * Provides two system tasks:
 *   $start_timer()  — captures a high-resolution start timestamp
 *   $stop_timer()   — captures stop timestamp, prints elapsed nanoseconds
 *                     as "$ELAPSED_NS:<value>" to stdout so Python can parse it.
 *
 * Purpose: isolate the pure simulation loop time from:
 *   - OS process spawn overhead
 *   - vvp VM initialisation
 *   - $readmemb disk I/O
 *   - process teardown
 *
 * Build (Windows, via iverilog-vpi):
 *   iverilog-vpi.exe vpi_timer.c
 *   (run from harness_build/ — produces vpi_timer.vpi in the same directory)
 *
 * Usage in testbench:
 *   $start_timer();
 *   for (i = 0; i < N; i = i + 1) begin ... end
 *   $stop_timer();
 *
 * Load with vvp:
 *   vvp -M<harness_dir> -mvpi_timer sim.vvp
 */

#include <vpi_user.h>
#include <windows.h>
#include <stdio.h>

static LARGE_INTEGER _t_start;
static LARGE_INTEGER _t_freq;
static int           _freq_cached = 0;

/* ------------------------------------------------------------------ */
/* $start_timer()                                                       */
/* ------------------------------------------------------------------ */
static PLI_INT32 start_timer_calltf(PLI_BYTE8 *user_data)
{
    (void)user_data;
    if (!_freq_cached) {
        QueryPerformanceFrequency(&_t_freq);
        _freq_cached = 1;
    }
    QueryPerformanceCounter(&_t_start);
    return 0;
}

static PLI_INT32 start_timer_compiletf(PLI_BYTE8 *user_data)
{
    (void)user_data;
    return 0;
}

/* ------------------------------------------------------------------ */
/* $stop_timer()                                                        */
/* ------------------------------------------------------------------ */
static PLI_INT32 stop_timer_calltf(PLI_BYTE8 *user_data)
{
    (void)user_data;
    LARGE_INTEGER t_end;
    QueryPerformanceCounter(&t_end);

    /* Compute elapsed nanoseconds via QPC frequency */
    long long elapsed_counts = t_end.QuadPart - _t_start.QuadPart;
    long long elapsed_ns = (elapsed_counts * 1000000000LL) / _t_freq.QuadPart;

    /* Print in a machine-parseable format so Python can extract it */
    vpi_printf("$ELAPSED_NS:%lld\n", elapsed_ns);
    return 0;
}

static PLI_INT32 stop_timer_compiletf(PLI_BYTE8 *user_data)
{
    (void)user_data;
    return 0;
}

/* ------------------------------------------------------------------ */
/* Registration                                                         */
/* ------------------------------------------------------------------ */
static void register_tasks(void)
{
    s_vpi_systf_data start_tf = {
        vpiSysTask,              /* type */
        0,                       /* sysfunctype */
        "$start_timer",          /* tfname */
        start_timer_calltf,      /* calltf */
        start_timer_compiletf,   /* compiletf */
        0,                       /* sizetf */
        0                        /* user_data */
    };

    s_vpi_systf_data stop_tf = {
        vpiSysTask,
        0,
        "$stop_timer",
        stop_timer_calltf,
        stop_timer_compiletf,
        0,
        0
    };

    vpi_register_systf(&start_tf);
    vpi_register_systf(&stop_tf);
}

/* VPI bootstrap table — loaded by vvp at startup */
void (*vlog_startup_routines[])(void) = {
    register_tasks,
    0
};
