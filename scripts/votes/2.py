# epoch 1 vote calculations

from ape import accounts, Contract
import json
from votes._common import *

CHOICES = 6
ASSET_NAMES = ['sfrxETH', 'swETH', 'wstETH', 'ETHx', 'cbETH', 'mevETH']
PREV_WEIGHTS = [2657, 2528, 2363, 1382, 1070, 0]
REDISTRIBUTE = UNIT//10

def main():
    total, votes = read_multiple_choice('votes/2-weight.csv', CHOICES)
    redistribute(total, votes)

    total, votes = read_multiple_choice('votes/2-inclusion.csv', 4)
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
        weights.append(round(w * 10000 / UNIT))

    weights = [w * 99 // 100 for w in weights]

    # fix rounding manually
    weights[0] += 1
    weights[1] += 1

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

    # incentive for including mevETH
    id = '0x0201000000000000000000000000000000000000000000000000000000000000'
    amts = [
        420_690000000000000000,
          1_000000000000000000,
          6_706259604852234882,
         15_000000000000000000,
    ]
    tokens = [
        '0xd084944d3c05CD115C09d072B9F44bA3E0E45921', # FOLD
        '0x0bc529c00C6401aEF6D220BE8C6Ea1667F6Ad93e', # YFI
        '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2', # WETH
        '0x24Ae2dA0f361AA4BE46b48EB19C91e02c5e4f27E', # mevETH
    ]
    ids = [f'{id[:-1]}{i}' for i in range(len(amts))]
    bootstrap_weight = 564850861950362944

    yeth_price = 1800
    prices = [10.7, 5700, 1800, 1800]
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
    id2 = '0x0201000000000000000000000000000000000000000000000000000000000004'
    account = '0x962d00611208f83175dA312277925b88E44708c7'
    amt = 21000000000
    token = '0xdAC17F958D2ee523a2206206994597C13D831ec7'

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

    f = open('votes/2.json', 'w')
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
