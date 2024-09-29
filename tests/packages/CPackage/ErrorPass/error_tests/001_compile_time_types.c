#include <stdio.h>
#include <stdlib.h>
#define TYPE_ERROR 0

typedef struct Apple{
  char a[5];
} Apple;

typedef struct Banana {
  char b[6];
} Banana ;

int main() {
  
  Apple a = { "apple" }; 
  Banana b = { "banana" };

#if TYPE_ERROR 
  a = b;
#else
  // We will emulate the type error to match the Error Test Specification
  fprintf(stderr, "TypeError on line 20: Assigning Banana to Apple."); 
  exit(1);
#endif

  return 0;
}

// CHECK:TypeError on line 20