/**
 * Instead of acutally throwing a runtime C error, whose format does not align with 
 * how the tester parses error tests, emulate the Gazprea spec.  
*/

#include <stdio.h>
#include <stdlib.h>

#define EXIT_DIVIDE_BY_ZERO 2

int main() {
    int a = 1;
    int b = 0;
    if (b != 0) {
        int c = a / b;
    } else {
        fprintf(stderr, "DivideByZeroError: a was about to be divided by 0!");
        exit(EXIT_DIVIDE_BY_ZERO);
    }  
    
    return 0;
}

//CHECK:DivideByZeroError:
