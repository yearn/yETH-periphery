# epoch 1 vote calculations

from ape import accounts, Contract
import json
from votes._common import *

ASSET_NAMES = ['sfrxETH', 'swETH', 'wstETH', 'ETHx', 'cbETH']
PREV_WEIGHTS = [2676, 2602, 2459, 1198, 1065]
REDISTRIBUTE = UNIT//10

def main():
    total, votes = read_multiple_choice('votes/1-weight.csv', len(ASSET_NAMES)+1)

    redistribute(total, votes)
    incentives(total, votes)

def redistribute(total, votes):
    assert sum(PREV_WEIGHTS) == 10000
    choices = len(ASSET_NAMES)+1
    results = multiple_choice_result(votes, choices)
    print('results:')
    for i, result in enumerate(results):
        name = ASSET_NAMES[i-1] if i > 0 else 'blank'
        print(f'{name.rjust(7)}: {result/total*100:.2f}%')

    redistribute = REDISTRIBUTE * (UNIT - results[0] * UNIT // total) // UNIT
    print(f'\nredistribute: {redistribute/UNIT*100:.2f}%\n')

    weights = []
    for i in range(1, choices):
        w = PREV_WEIGHTS[i-1] * (UNIT - redistribute) // 10000
        w += results[i] * redistribute // (total - results[0])
        weights.append(round(w * 10000 / UNIT))
    weights[4] -= 1 # fix rounding manually
    assert sum(weights) == 10000

    print('new weights:')
    for i, w in enumerate(weights):
        print(f'{ASSET_NAMES[i].rjust(7)}: {w/100:.2f}%')

def incentives(total, votes):
    print('\nincentives')
    mi = Contract(MERKLE_INCENTIVES)

    # incentive for voting on swETH
    id = '0x0102000000000000000000000000000000000000000000000000000000000000'
    choice = 2
    amt = UNIT
    token = '0xf951E335afb289353dc249e82926178EaC7DEd78' # swETH

    total, votes = filter_votes(votes, choice)
    for account, vote in votes.items():
        votes[account] = amt * vote // total
        print(f'{account}: {votes[account]/UNIT}')
    
    leaves = build_leaves(votes, token)
    tree, root = build_tree(leaves)
    print(f'\naccounts: {len(leaves)}')
    print(f'root: {root.hex()}')

    proofs = {}
    for i, (account, vote) in enumerate(votes.items()):
        if account not in proofs:
            proofs[account] = []
        proofs[account].append({
            'vote': id,
            'incentive': token,
            'amount': vote,
            'proof': build_proof(tree, i)
        })

    # refund incentive for including mpETH
    id2 = '0x0101000000000000000000000000000000000000000000000000000000000000'
    account = '0x962d00611208f83175dA312277925b88E44708c7'
    amt = 2 * UNIT
    token = '0x583019fF0f430721aDa9cfb4fac8F06cA104d0B4'

    leaf = [account, token, amt]
    tree2, root2 = build_tree([leaf, leaf])
    print(f'refund root: {root2.hex()}')
    if account not in proofs:
        proofs[account] = []
    proofs[account].append({
        'vote': id2,
        'incentive': token,
        'amount': amt,
        'proof': [tree2[0][0].hex()]
    })

    f = open('votes/1.json', 'w')
    json.dump(proofs, f, indent=2)
    f.write('\n')

    # test claiming
    mgmt = accounts[mi.management()]
    alice = accounts.test_accounts[0]
    alice.transfer(mgmt, UNIT)
    mi.set_root(id, root, sender=mgmt)
    mi.set_root(id2, root2, sender=mgmt)
    
    for account, acc_proofs in proofs.items():
        for proof in acc_proofs:
            incentive = Contract(proof['incentive'])
            pre = incentive.balanceOf(account)
            mi.claim(proof['vote'], proof['incentive'], proof['amount'], proof['proof'], account, sender=alice)
            assert incentive.balanceOf(account) - pre == proof['amount']
