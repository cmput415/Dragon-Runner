#include <stdio.h>
#include <stdlib.h>

// INPUT:abc

int main() {
    char c[3];
    scanf("%c", &c[0]);
    scanf("%c", &c[1]);
    scanf("%c", &c[2]);

    printf("%c%c%c", c[2], c[1], c[0]);

    return 0;
}

// CHECK:cba