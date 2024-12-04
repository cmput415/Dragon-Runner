#include <stdlib.h>
#include <stdio.h>

#define ARRAY_SIZE 4096

int main() { 
    
    int *big_arr = malloc(sizeof(int) * 1);
    
    printf("NO FREE");

    return 0;
}

// CHECK:This test has no leaks...
