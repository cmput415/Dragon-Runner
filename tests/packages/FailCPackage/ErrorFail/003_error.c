#include <stdio.h>
#include <stdlib.h>

// An error test that does not provide a check for the expected output.

int main() {

    fprintf(stderr, "TypeError on line 5: This is an error!");
    exit(1);
    return 0;
}
