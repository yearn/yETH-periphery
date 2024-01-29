# epoch 1 vote calculations

from ape import accounts, Contract
import json
from votes._common import *

CHOICES = 8
ASSET_NAMES = ['sfrxETH', 'swETH', 'wstETH', 'ETHx', 'cbETH', 'mevETH', 'rETH', 'apxETH']
PREV_WEIGHTS = [2356, 1874, 1883, 1309, 991, 996, 591, 0]
REDISTRIBUTE = UNIT//10

def main():
    total, votes = read_multiple_choice('votes/5-weight.csv', CHOICES)
    redistribute(total, votes)

    total, votes = read_multiple_choice('votes/5-inclusion.csv', 3)
    incentives(total, votes)

def redistribute(total, votes):
    assert sum(PREV_WEIGHTS) == 10000
    results = multiple_choice_result(votes, CHOICES)
    print('results:')
    for i, result in enumerate(results):
        name = ASSET_NAMES[i-1] if i > 0 else 'blank'
        print(f'{name.rjust(7)}: {result/total*100:.2f}%')

    redistribute = REDISTRIBUTE * (UNIT - results[0] * UNIT // total) // UNIT
    print(f'\nredistribute: {redistribute/UNIT*100:.2f}%\n')

    weights = []
    for i in range(1, CHOICES):
        w = PREV_WEIGHTS[i-1] * (UNIT - redistribute) // 10000
        w += results[i] * redistribute // (total - results[0])
        # print(w * 10000 / UNIT)
        weights.append(round(w * 10000 / UNIT))

    weights = [w * 99 // 100 for w in weights]

    # fix rounding manually
    weights[0] += 1
    weights[1] += 1
    weights[3] += 1
    weights[4] += 1
    weights[6] += 1

    weights.append(100)
    assert sum(weights) == 10000

    print('new weights:')
    for i, w in enumerate(weights):
        delta = w - PREV_WEIGHTS[i]
        sign = '+' if delta > 0 else ''
        print(f'{ASSET_NAMES[i].rjust(7)}: {w/100:.2f}% ({sign}{delta/100:.2f}%)')

def incentives(total, votes):
    print('\nincentives')
    mi = Contract(MERKLE_INCENTIVES)

    # incentive for including apxETH
    id = '0x0501000000000000000000000000000000000000000000000000000000000000'
    amts = [
        30_000000000000000000,
    ]
    tokens = [
        '0xc55126051B22eBb829D00368f4B12Bde432de5Da' # BTRFLY
    ]
    ids = [f'{id[:-1]}{i}' for i in range(len(amts))]
    bootstrap = Contract('0x7cf484D9d16BA26aB3bCdc8EC4a73aC50136d491')
    staking = Contract('0x583019fF0f430721aDa9cfb4fac8F06cA104d0B4')
    ts = 19050000
    bootstrap_weight = staking.vote_weight(bootstrap, block_id=ts) * UNIT // bootstrap.deposited(block_id=ts)

    yeth_price = 2250
    prices = [404]
    total_usd = 0
    for amt, price in zip(amts, prices):
        total_usd += amt / UNIT * price

    incentive_apr = total_usd * bootstrap_weight / total * 365 / 28 / yeth_price
    print(f'epoch incentive vAPR: {incentive_apr*100:.1f}%')

    leaves = []
    for token, amt in zip(tokens, amts):
        l = []
        for account, vote in votes.items():
            l.append([account, token, amt * sum(vote) // total])
        leaves.append(l)

    trees = []
    roots = []
    for l in leaves:
        tree, root = build_tree(l)
        trees.append(tree)
        roots.append(root)
    
    print(f'accounts: {len(votes)}')
    for root in roots:
        print(f'root: {root.hex()}')

    proofs = {}
    for j, l in enumerate(leaves):
        for i, leaf in enumerate(l):
            account, token, amt = leaf
            if account not in proofs:
                proofs[account] = []
            proofs[account].append({
                'vote': ids[j],
                'incentive': token,
                'amount': amt,
                'proof': build_proof(trees[j], i)
            })

    # refund incentive for including mpETH
    id2 = '0x0501000000000000000000000000000000000000000000000000000000000001'
    account1 = '0xEA26e7fC8ABE2D8Bd3A84ED207Ad9E0560E29901'
    amt1 = 10_000_000_000 + 100_000_000
    account2 = '0x962d00611208f83175dA312277925b88E44708c7'
    amt2 = 2_500_000_000
    token = '0xdAC17F958D2ee523a2206206994597C13D831ec7'

    leaf1 = [account1, token, amt1]
    leaf2 = [account2, token, amt2]
    tree2, root2 = build_tree([leaf1, leaf2])
    print(f'refund root: {root2.hex()}')
    if account1 not in proofs:
        proofs[account1] = []
    if account2 not in proofs:
        proofs[account2] = []
    proofs[account1].append({
        'vote': id2,
        'incentive': token,
        'amount': amt1,
        'proof': [tree2[0][1].hex()]
    })
    proofs[account2].append({
        'vote': id2,
        'incentive': token,
        'amount': amt2,
        'proof': [tree2[0][0].hex()]
    })

    f = open('votes/5.json', 'w')
    json.dump(proofs, f, indent=2)
    f.write('\n')

    # test claiming
    mgmt = accounts[mi.management()]
    alice = accounts.test_accounts[0]
    alice.transfer(mgmt, UNIT)
    for id, root in zip(ids, roots):
        mi.set_root(id, root, sender=mgmt)
    mi.set_root(id2, root2, sender=mgmt)
    
    print('test claims')
    for account, acc_proofs in proofs.items():
        for proof in acc_proofs:
            incentive = Contract(proof['incentive'])
            pre = incentive.balanceOf(account)
            mi.claim(proof['vote'], proof['incentive'], proof['amount'], proof['proof'], account, sender=alice)
            assert incentive.balanceOf(account) - pre == proof['amount']
