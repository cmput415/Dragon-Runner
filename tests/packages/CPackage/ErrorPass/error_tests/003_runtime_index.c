#include <stdio.h>
#include <stdlib.h>
#define OUT_OF_BOUNDS_ERROR 0

// INPUT:9
int main() {

    char c;
    scanf("%c", &c);

    int x = (unsigned int)(c) - '0'; 
    int a[5] = {1, 2, 3, 4, 5};

    if (x < 5 && x >= 0) {
        printf("%d", a[x]);
    } else {
        // We will emulate the IndexError to match "Error Test Spec" since
        // C will just let us poke around.
        fprintf(stderr, "IndexError: Don't do that! (The text past the first\
            colon is implementation specific so is not picked up by the tester)"); 
        
        exit(1);
    }
    
    return 0;
}

// CHECK:IndexError