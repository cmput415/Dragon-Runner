#include <stdio.h>

int main() {
  
  char nl = '\n';
  char space = ' ';
  char a = 'a'; 
  char mixed[11] = {
    nl, nl, space, space, a, 
    space, space, a, nl, space, a
  };
  
  for (int i = 0; i < 11; i++) {
    printf("%c", mixed[i]);
  }

  return 0;
}

//CHECK:
//CHECK:
//CHECK:  a  a
//CHECK: a
