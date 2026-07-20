/* Minimal single-header C test framework, styled after doctest's ergonomics: write
 * TEST_CASE(name) { CHECK(...); } with no main() and no manual registration. Works
 * across multiple .c files compiled together because the actual storage for the
 * global test/check counters lives in the bootstrapped sandbox_main.c (declared here
 * only as `extern`) -- each translation unit that uses TEST_CASE just registers into
 * those shared arrays via a constructor that runs before main().
 */
#ifndef SANDBOX_TEST_H
#define SANDBOX_TEST_H

#include <stdio.h>

typedef void (*sandbox_test_fn)(void);

#define SANDBOX_MAX_TESTS 256

extern sandbox_test_fn sandbox_tests[SANDBOX_MAX_TESTS];
extern const char *sandbox_test_names[SANDBOX_MAX_TESTS];
extern int sandbox_test_count;
extern int sandbox_checks_run;
extern int sandbox_checks_failed;
extern int sandbox_current_test_failed;

void sandbox_register_test(sandbox_test_fn fn, const char *name);

#define TEST_CASE(name) \
    static void name(void); \
    __attribute__((constructor)) static void sandbox_register_##name(void) { \
        sandbox_register_test(name, #name); \
    } \
    static void name(void)

#define CHECK(condition) \
    do { \
        sandbox_checks_run++; \
        if (!(condition)) { \
            sandbox_checks_failed++; \
            sandbox_current_test_failed = 1; \
            printf("  FAIL %s:%d: CHECK(%s)\n", __FILE__, __LINE__, #condition); \
        } \
    } while (0)

#endif
