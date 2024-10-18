#include <stdio.h>

// Runtime config must supply the definition for fib
// **at runtime**

int square(int n);

int main() {

    printf("%d\n", square(8));
    return 0;
}

//CHECK:64
//CHECK: