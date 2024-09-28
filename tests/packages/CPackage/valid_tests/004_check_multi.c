#include <stdio.h>

#define MAX_ITER 5
int main() {

  for (int i = 0; i < MAX_ITER; i++) {
    printf("%d", i);
    if (i != MAX_ITER-1) {
      printf("\n"); 
    }
  }

  return 0;
}
  
//CHECK:0
//CHECK:1
//CHECK:2
//CHECK:3
//CHECK:4
