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
