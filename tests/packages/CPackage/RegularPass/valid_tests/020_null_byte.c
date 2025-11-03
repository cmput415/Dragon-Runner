#include <stdio.h>
#include <stdbool.h>

int main() { 
    char hi = (char)(false);
    printf("%c", hi);
}


//CHECK_FILE:out-stream/020_null_byte.out
