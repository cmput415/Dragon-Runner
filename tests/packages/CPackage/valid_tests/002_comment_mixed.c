
// below is a line comment
// INPUT:a
// INPUT:bc

#include <stdio.h>

int main() {
    
    char carr[1024]; 
    char c;
    
    scanf("%c", &c);
    printf("%c\n", c);
    scanf("%c", &c); // consume newline

    fgets(carr, 1024, stdin);
    printf("%s", carr);
    
    return 0;
}

// CHECK:a
// CHECK:bc
