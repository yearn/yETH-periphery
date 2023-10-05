from ape import Contract

MERKLE_INCENTIVES = '0xAE9De8A3e62e8E2f1e3800d142D23527680a5179'
UNIT = 1_000_000_000_000_000_000

def read_multiple_choice(name, choices):
    out = {}
    f = open(name)
    f.readline()
    line = f.readline()
    total = 0
    while line:
        parts = line.split(',')
        line = f.readline()

        account = parts[0]
        i = 0
        points = []
        for i in range(1, choices+1):
            points.append(float(parts[i]) if parts[i] != '' else float(0))
        points_sum = sum(points)
        weight = int(float(parts[choices+1]) * UNIT)
        for i in range(choices):
            points[i] = int(weight * points[i] / points_sum)
        out[account] = points
        
        total += sum(points)
    return total, out

def multiple_choice_result(votes, choices):
    results = [0 for _ in range(choices)]
    for _, vote in votes.items():
        for i in range(choices):
            results[i] += vote[i]
    return results

def filter_votes(votes, choice):
    total = 0
    out = {}
    for account, vote in votes.items():
        if vote[choice] > 0:
            out[account] = vote[choice]
            total += vote[choice]
    return total, out

def build_leaves(votes, token):
    leaves = []
    for account, vote in votes.items():
        leaves.append([account, token, vote])
    return leaves

def build_tree(leaves):
    incentives = Contract(MERKLE_INCENTIVES)
    tree = []
    hashes = []
    for leaf in leaves:
        hashes.append(incentives.leaf(leaf[0], leaf[1], leaf[2]))
    n = len(hashes)
    if n == 1:
        hashes.append(hashes[0])
        n += 1
    
    while n > 1:
        if n % 2 == 1:
            hashes.append(hashes[len(hashes)-1])
            n += 1
    
        tree.append(hashes)
        next = []
        for i in range(n//2):
            j = 2*i
            left = hashes[j]
            j = 2*i + 1
            right = hashes[j] if j < n else hashes[j-1]
            next.append(incentives.hash_siblings(left, right))
        hashes = next
        n = len(hashes)

    return tree, hashes[0]

def build_proof(tree, i):
    proof = []
    for level in tree:
        j = i + 1 if i % 2 == 0 else i - 1
        proof.append(level[j].hex())
        i = i // 2
    return proof
