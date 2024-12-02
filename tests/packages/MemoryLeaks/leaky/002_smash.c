
#include <stdlib.h>
#include <stdio.h>

void create_leak() {
    int *array = malloc(10 * sizeof(int));
    for (int i = 0; i < 10; i++) {
        array[i] = i; // Use the allocated memory
    }
    // Simulating forgetting the pointer
    array = NULL;
}

int main() {
    create_leak();
    printf("Memory leaked"); //CHECK:Memory leaked
    return 0;
}
