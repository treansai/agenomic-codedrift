import urllib.request
def get(u):
    r = urllib.request.urlopen(u)
    d = r.read()
    return d.decode()
