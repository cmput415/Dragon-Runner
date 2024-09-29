
#include <stdio.h>

int main() {
  
  /*
   * We can supply the std input to the array by 
   * where the array is declared.
   * */
  
  //INPUT:0,1,2,3,4,5,6,7,8,9
  int array[10];
  
  for (int i = 0; i < 10; i++) {
    char digit;
    scanf("%c", &digit);
    if (digit == ',') {
      i--;
      continue;
    }
    array[i] = (int)(digit - '0');
  }

  for (int i=0; i < 10; i++) {
    printf("%d", array[i] + 100);
    if (i != 9) {
      printf(", ");
    } 
  }
  //CHECK:100, 101, 102, 103, 104, 105, 106, 107, 108, 109
  
  /*
   * We can check the expected output right where we expect it!
   * (It doesn't actually mater where we place any of these directives)
   * */
 
  return 0;
}

