// INPUT_FILE:./in-stream/003_input_file.ins

#include <stdio.h>

int main() {
  char line[1024];

  while (fgets(line, sizeof(line), stdin)) {
    // Process each line
    int value1, value2;
    float value3;
    
    if (sscanf(line, "%d %d %f", &value1, &value2, &value3) == 3) {
        printf("%d, %d, %.2f\n", value1, value2, value3);
    }
  }

  return 0;
}

// CHECK:10, 20, 3.14
// CHECK:15, 30, 2.71
// CHECK:22, 11, 1.41
// CHECK:8, 5, 0.99
// CHECK: