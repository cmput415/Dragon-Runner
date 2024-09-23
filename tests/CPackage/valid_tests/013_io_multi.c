// INPUT:a
// INPUT:b

#include <stdio.h>

int main(int argc, char **argv) {
  
  char a, b;
  char nl;

  scanf("%c", &a);
  scanf("%c", &nl); // consume nl
  scanf("%c", &b);

  printf("%c\n", a);
  printf("%c\n", b);

  printf("c");
  return 0;
}

// CHECK:a
// CHECK:b
// CHECK:c