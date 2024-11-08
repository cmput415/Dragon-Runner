/**
 * Check for a different type of error than is rasied at runtime.
 * This will still pass because the error parsing is lenient. 
 */

#include <stdio.h>
#include <stdlib.h>

#define TYPE_ERROR 1

int main() {

    fprintf(stderr, "SpecificError on line 12: compile time error"); 
    
    exit(1);
    
    return 0;
}

//CHECK:SpecificError on line 12
