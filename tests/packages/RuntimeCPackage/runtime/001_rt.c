#include <stdio.h>

// Runtime config must supply the definition for fib
// **at runtime**

int fib(int n);

int main() {

    printf("%d\n", fib(8));
    return 0;
}

//CHECK:21
//CHECK: