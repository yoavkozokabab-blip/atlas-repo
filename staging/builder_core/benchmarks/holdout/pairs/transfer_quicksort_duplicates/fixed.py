def quicksort(values):
    if len(values) <= 1:
        return values
    pivot = values[0]
    left = [value for value in values if value < pivot]
    middle = [value for value in values if value == pivot]
    right = [value for value in values if value > pivot]
    return quicksort(left) + middle + quicksort(right)
