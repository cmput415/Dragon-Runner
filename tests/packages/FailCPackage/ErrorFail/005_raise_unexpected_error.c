
#include <stdio.h>

int main() {
    
    if (1) {
        fprintf(stderr, "SizeError: Catastrophic failure...");
        return 1; 
    }
    
    printf("Everything is fine...");
    return 0;
}

// CHECK:Everything is fine...

