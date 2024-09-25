
// This test is dangerous because the INPUT parser can easily consume the
// block comment terminator '*/' since it lies on the same line. 

// INPUT:a           8

#include <stdio.h>

int main() {
    char c;
    scanf("%c", &c);
    printf("%c", c);
    
    int x; 
    scanf("%d", &x);
    printf("%d", x);
    return 0;
}

// CHECK:a8
