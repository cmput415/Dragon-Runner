#include <stdlib.h>
#include <stdio.h>

#define ARRAY_SIZE 4096

int main() {

    // `volatile` prevents the compiler from eliding the allocation as
    // dead code — otherwise modern gcc optimizes malloc away entirely
    // and valgrind sees nothing to leak.
    volatile int *big_arr = malloc(sizeof(int) * ARRAY_SIZE);
    big_arr[0] = 42;

    printf("NO FREE");

    return 0;
}

// CHECK:NO FREE
