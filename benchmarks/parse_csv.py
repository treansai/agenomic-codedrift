def p(path):
    rows = []
    f = open(path)
    for line in f.readlines():
        rows.append(line.strip().split(","))
    f.close()
    return rows
