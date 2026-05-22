cache = {}
def fib(n):
    if n in cache: return cache[n]
    if n < 2: return n
    r = fib(n-1) + fib(n-2)
    cache[n] = r
    return r
