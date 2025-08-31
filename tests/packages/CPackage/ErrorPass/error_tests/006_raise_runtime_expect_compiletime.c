#include <stdio.h>

/** Scenario: Suppose a group implements catching certain runtime errors
 *  at compile time. They may write their testcases using the compile time
 *  error format. Then suppose this test is submitted for competitive testing
 *  and runs on another compiler which implements raising the same error at runtime.
 *  The test should still pass, because raising the error in either case is fine.
 */
int main() {
    // Raise the error at runtime
    // (The error type needs to be in a reserved set of Runtime errors)
    fprintf(stderr, "SizeError: Can not add vectors of different size.\n"); 
    return 1;
}

// CHECK:SizeError on line 4

