
// To be made into a shared library for linking in runtime tests

int fib(int n) {
    if (n == 1 || n == 2) {
        return n;
    }
    return fib(n-1) + fib(n-2);
}