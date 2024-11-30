#include <stdlib.h>
#include <stdio.h>

#define ARRAY_SIZE 4096

int main() { 
    
    int *big_arr = malloc(sizeof(int) * 4096);
    
    // FREE

    free(big_arr);
    
    printf("BE FREE");

    return 0;
}

// CHECK:BE FREE
