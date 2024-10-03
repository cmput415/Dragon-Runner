#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/wait.h>
#include <sys/types.h>
#include <time.h>


int main() {

    pid_t pid = fork();
    
    if (pid == -1) {
        perror("fork");
        exit(EXIT_FAILURE);
    }
    if (pid == 0) {
        // child process
        printf("Child taking a nap.\n");
        sleep(1); 
        exit(EXIT_SUCCESS);
    }

    int status;
    waitpid(pid, &status, 0);
    printf("Parent has waited paitiently.\n");

    return 0;
}

// CHECK:Child taking a nap.
// CHECK:Parent has waited paitiently.
// CHECK: