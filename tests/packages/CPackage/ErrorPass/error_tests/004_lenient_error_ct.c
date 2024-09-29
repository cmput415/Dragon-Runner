/**
 * Check for a different type of error than is rasied at compile time.
 * This will still pass because the error parsing is lenient. 
 */

#include <stdio.h>
#include <stdlib.h>

#define TYPE_ERROR 1

int main() { 
    int a = 4; 
#if TYPE_ERROR
    fprintf(stderr, "RandomTypeOfError on line 9: This should be called a TypeError, but\
                     the tester is lenient on the type of error. See TestRunning.cpp");
    exit(1);
#else
    a = "this is a string";
#endif
}

//CHECK:TypeError on line 9