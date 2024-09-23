
// This test is dangerous because the INPUT parser can easily consume the
// block comment terminator '*/' since it lies on the same line. 

/*INPUT:a*/

#include <stdio.h>

int main() {
    char c;
    scanf("%c", &c);
    printf("%c", c);
    return 0;
}

// CHECK:a
