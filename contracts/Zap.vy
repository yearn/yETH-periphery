# @version 0.3.7
"""
@title yETH stake zap
@author 0xkorin, Yearn Finance
@license Copyright (c) Yearn Finance, 2023 - all rights reserved
"""

from vyper.interfaces import ERC20
from vyper.interfaces import ERC4626

interface Pool:
    def num_assets() -> uint256: view
    def assets(_i: uint256) -> address: view
    def add_liquidity(_amounts: DynArray[uint256, 32], _min_lp_amount: uint256, _receiver: address) -> uint256: nonpayable

token: public(immutable(address))
pool: public(immutable(address))
staking: public(immutable(address))

@external
def __init__(_token: address, _pool: address, _staking: address):
    """
    @notice Constructor
    @param _token Token contract address
    @param _pool Pool contract address
    @param _staking Staking contract address
    """
    token = _token
    pool = _pool
    staking = _staking

    assert ERC20(token).approve(staking, max_value(uint256), default_return_value=True)

@external
def approve(_i: uint256):
    """
    @notice Approve transfer of a pool asset to the pool
    @param _i Index of the pool asset to approve
    """
    asset: address = Pool(pool).assets(_i)
    assert ERC20(asset).approve(pool, max_value(uint256), default_return_value=True)

@external
def add_liquidity(
    _amounts: DynArray[uint256, 32], 
    _min_lp_amount: uint256, 
    _receiver: address = msg.sender
) -> (uint256, uint256):
    """
    @notice Deposit assets into the pool and stake
    @param _amounts Array of amount for each asset to take from caller
    @param _min_lp_amount Minimum amount of LP tokens to mint
    @param _receiver Account to receive the LP tokens
    @return Tuple with the amount of LP tokens minted and the amount of staking shares minted
    """
    num_assets: uint256 = Pool(pool).num_assets()
    for i in range(32):
        if i == num_assets:
            break
        amount: uint256 = _amounts[i]
        if amount == 0:
            continue
        asset: address = Pool(pool).assets(i)
        assert ERC20(asset).transferFrom(msg.sender, self, amount, default_return_value=True)

    lp_amount: uint256 = Pool(pool).add_liquidity(_amounts, _min_lp_amount, self)
    shares: uint256 = ERC4626(staking).deposit(lp_amount, _receiver)
    return lp_amount, shares
