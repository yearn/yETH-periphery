import ape
import pytest
from random import randbytes

MAX = 2**256 - 1

def build_tree(incentives, leaves):
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
        proof.append(level[j])
        i = i // 2
    return proof

def tokens(project, deployer, n):
    tokens = []
    for _ in range(n):
        tokens.append(project.MockToken.deploy(sender=deployer))
    if n == 1:
        return tokens[0]
    return tokens

@pytest.fixture
def alice(accounts):
    return accounts[1]

@pytest.fixture
def incentives(project, deployer):
    return project.MerkleIncentives.deploy(sender=deployer)

def test_deposit(project, deployer, alice, incentives):
    vote = randbytes(32)
    token = tokens(project, deployer, 1)
    token.approve(incentives, MAX, sender=alice)
    token.mint(alice, 1, sender=alice)

    incentives.deposit(vote, 1, token, 1, sender=alice)
    assert token.balanceOf(incentives) == 1

def test_deposit_failures(project, deployer, alice, incentives):
    vote = randbytes(32)
    token = tokens(project, deployer, 1)
    token.approve(incentives, MAX, sender=alice)
    token.mint(alice, 1, sender=alice)

    # vote id 0
    with ape.reverts():
        incentives.deposit(bytes(0), 1, token, 1, sender=alice)
    
    # choice 0
    with ape.reverts(dev_message='dev: 1-indexed'):
        incentives.deposit(vote, 0, token, 1, sender=alice)

    # zero amount
    with ape.reverts():
        incentives.deposit(vote, 1, token, 0, sender=alice)

    # after root has been submitted
    incentives.set_root(vote, vote, sender=deployer)
    with ape.reverts(dev_message='dev: vote concluded'):
        incentives.deposit(vote, 1, token, 1, sender=alice)

def test_claim(project, deployer, accounts, incentives):
    vote = randbytes(32)
    token = tokens(project, deployer, 1)
    token.approve(incentives, MAX, sender=deployer)
    token.mint(deployer, 15, sender=deployer)
    incentives.deposit(vote, 1, token, 15, sender=deployer)

    # build tree and submit root
    leaves = [[accounts[i], token, i] for i in range(1, 6)]
    tree, root = build_tree(incentives, leaves)
    incentives.set_root(vote, root, sender=deployer)

    # claim for each recipient
    for i in range(1, 6):
        proof = build_proof(tree, i-1)
        incentives.claim(vote, token, i, proof, accounts[i], sender=deployer)
        assert token.balanceOf(accounts[i]) == i

def test_claim_twice(project, deployer, accounts, incentives):
    vote = randbytes(32)
    token = tokens(project, deployer, 1)
    token.approve(incentives, MAX, sender=deployer)
    token.mint(deployer, 15, sender=deployer)
    incentives.deposit(vote, 1, token, 15, sender=deployer)

    leaves = [[accounts[i], token, i] for i in range(1, 6)]
    tree, root = build_tree(incentives, leaves)
    incentives.set_root(vote, root, sender=deployer)

    proof = build_proof(tree, 0)
    incentives.claim(vote, token, 1, proof, accounts[1], sender=deployer)
    with ape.reverts(dev_message='dev: already claimed'):
        incentives.claim(vote, token, 1, proof, accounts[1], sender=deployer)
