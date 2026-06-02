from collections import deque


def bfs(graph, start, goal):
    queue = deque([start])
    while queue:
        node = queue.popleft()
        if node == goal:
            return True
        for neighbor in graph.get(node, []):
            queue.append(neighbor)
    return False
