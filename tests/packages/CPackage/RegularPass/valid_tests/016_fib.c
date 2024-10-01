int fib(int n) {
    
    if (n == 0 || n == 1)
        return n;

    return fib(n-1) + fib(n-2);
}

int main() {
    int result=fib(12);
    return 0;
}