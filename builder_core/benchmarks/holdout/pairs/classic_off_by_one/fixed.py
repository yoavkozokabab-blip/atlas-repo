def last_index(items):
    for index in range(len(items)):
        if items[index] == items[-1]:
            return index
    return -1
