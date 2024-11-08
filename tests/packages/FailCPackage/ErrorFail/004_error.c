#include <stdio.h>
#include <stdlib.h>

// An error test that provides a check but for a different line

int main() {

    fprintf(stderr, "TypeError on line 5: This is an error!");
    exit(1);
    return 0;
}

//CHECK:WrongError on line 6
