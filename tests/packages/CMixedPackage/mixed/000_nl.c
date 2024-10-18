#include <stdio.h>

/// This will fail since there is an extra newline emitted.
/// The expected file will have 5 bytes, the generated will have 6

int main() {
    
    printf("a\nb\nc\n");

    return 0;
}

//CHECK:a
//CHECK:b
//CHECK:c