# @version 0.3.10
"""
@title yETH delegated staking contract
@author 0xkorin, Yearn Finance
@license Copyright (c) Yearn Finance, 2023 - all rights reserved
"""

from vyper.interfaces import ERC20
from vyper.interfaces import ERC4626
implements: ERC20
implements: ERC4626

interface Measure:
    def total_vote_weight() -> uint256: view
    def vote_weight(_account: address) -> uint256: view
implements: Measure

last_supply: public(uint256)
last_balances: public(HashMap[address, uint256])

# ERC20 state
totalSupply: public(uint256)
balanceOf: public(HashMap[address, uint256])
allowance: public(HashMap[address, HashMap[address, uint256]])

name: public(constant(String[28])) = "Delegated Staked Yearn Ether"
symbol: public(constant(String[9])) = "d-st-yETH"
decimals: public(constant(uint8)) = 18

# ERC4626 state
asset: public(immutable(address))

# ERC20 events
event Transfer:
    sender: indexed(address)
    receiver: indexed(address)
    value: uint256

event Approval:
    owner: indexed(address)
    spender: indexed(address)
    value: uint256

# ERC4626 events
event Deposit:
    sender: indexed(address)
    owner: indexed(address)
    assets: uint256
    shares: uint256

event Withdraw:
    sender: indexed(address)
    receiver: indexed(address)
    owner: indexed(address)
    assets: uint256
    shares: uint256

WEEK_LENGTH: constant(uint256) = 7 * 24 * 60 * 60
WEEK_MASK: constant(uint256) = 2**16 - 1
BAL_SHIFT: constant(int128) = -16
BAL_MASK: constant(uint256) = 2**240 - 1
INCREMENT: constant(bool) = True
DECREMENT: constant(bool) = False

@external
def __init__(_asset: address):
    """
    @notice Constructor
    @param _asset The underlying asset
    """
    assert _asset != empty(address)
    asset = _asset
    log Transfer(empty(address), msg.sender, 0)

@external
def transfer(_to: address, _value: uint256) -> bool:
    """
    @notice Transfer to another account
    @param _to Account to transfer to
    @param _value Amount to transfer
    @return True
    """
    assert _to != empty(address) and _to != self
    if _value > 0:
        self._update_last(msg.sender)
        self._update_last(_to)

        self.balanceOf[msg.sender] -= _value        
        self.balanceOf[_to] += _value
    log Transfer(msg.sender, _to, _value)
    return True

@external
def transferFrom(_from: address, _to: address, _value: uint256) -> bool:
    """
    @notice Transfer from one account to another account
    @param _from Account to transfe from
    @param _to Account to transfer to
    @param _value Amount to transfer
    @return True
    """
    assert _to != empty(address) and _to != self
    self.allowance[_from][msg.sender] -= _value
    if _value > 0:
        self._update_last(_from)
        self._update_last(_to)

        self.balanceOf[_from] -= _value
        self.balanceOf[_to] += _value
    log Transfer(_from, _to, _value)
    return True

@external
def approve(_spender: address, _value: uint256) -> bool:
    """
    @notice Approve another account to spend. Beware that changing an allowance 
        with this method brings the risk that someone may use both the old and 
        the new allowance by unfortunate transaction ordering. 
        See https://github.com/ethereum/EIPs/issues/20#issuecomment-263524729
    @param _spender Account that is allowed to spend
    @param _value Amount that the spender is allowed to transfer
    @return Flag indicating whether the approval was successful
    """
    assert _spender != empty(address)
    self.allowance[msg.sender][_spender] = _value
    log Approval(msg.sender, _spender, _value)
    return True

@external
def increaseAllowance(_spender: address, _value: uint256) -> bool:
    """
    @notice Increase the allowance of another account to spend. This method mitigates 
        the risk that someone may use both the old and the new allowance by unfortunate 
        transaction ordering.
        See https://github.com/ethereum/EIPs/issues/20#issuecomment-263524729
    @param _spender Account that is allowed to spend
    @param _value The amount of tokens to increase the allowance by
    @return True
    """
    assert _spender != empty(address)
    allowance: uint256 = self.allowance[msg.sender][_spender] + _value
    self.allowance[msg.sender][_spender] = allowance
    log Approval(msg.sender, _spender, allowance)
    return True

@external
def decreaseAllowance(_spender: address, _value: uint256) -> bool:
    """
    @notice Decrease the allowance of another account to spend. This method mitigates 
        the risk that someone may use both the old and the new allowance by unfortunate 
        transaction ordering.
        See https://github.com/ethereum/EIPs/issues/20#issuecomment-263524729
    @param _spender Account that is allowed to spend
    @param _value The amount of tokens to decrease the allowance by
    @return True
    """
    assert _spender != empty(address)
    allowance: uint256 = self.allowance[msg.sender][_spender]
    if _value > allowance:
        allowance = 0
    else:
        allowance -= _value
    self.allowance[msg.sender][_spender] = allowance
    log Approval(msg.sender, _spender, allowance)
    return True

# ERC4626 functions
@external
@view
def totalAssets() -> uint256:
    """
    @notice Get the total assets in the contract
    @return Total assets in the contract
    """
    return self.totalSupply

@external
@view
def convertToShares(_assets: uint256) -> uint256:
    """
    @notice Convert amount of assets to amount of shares
    @param _assets Amount of assets
    @return Amount of shares
    """
    return _assets

@external
@view
def convertToAssets(_shares: uint256) -> uint256:
    """
    @notice Convert amount of shares to amount of assets
    @param _shares Amount of shares
    @return Amount of assets
    """
    return _shares

@external
@view
def maxDeposit(_receiver: address) -> uint256:
    """
    @notice Get the maximum amount of assets an account is allowed to deposit
    @param _receiver Account
    @return Maximum amount the account is allowed to deposit
    """
    return max_value(uint256)

@external
@view
def previewDeposit(_assets: uint256) -> uint256:
    """
    @notice Simulate the effect of a deposit
    @param _assets Amount of assets to deposit
    @return Amount of shares that will be minted
    """
    return _assets

@external
def deposit(_assets: uint256, _receiver: address = msg.sender) -> uint256:
    """
    @notice Deposit assets
    @param _assets Amount of assets to deposit
    @param _receiver Account that will receive the shares
    @return Amount of shares minted
    """
    self._deposit(_assets, _receiver)
    return _assets

@external
@view
def maxMint(_receiver: address) -> uint256:
    """
    @notice Get the maximum amount of shares an account is allowed to mint
    @param _receiver Account
    @return Maximum amount the account is allowed to mint
    """
    return max_value(uint256)

@external
@view
def previewMint(_shares: uint256) -> uint256:
    """
    @notice Simulate the effect of a mint
    @param _shares Amount of shares to mint
    @return Amount of assets that will be taken
    """
    return _shares

@external
def mint(_shares: uint256, _receiver: address = msg.sender) -> uint256:
    """
    @notice Mint shares
    @param _shares Amount of shares to mint
    @param _receiver Account that will receive the shares
    @return Amount of assets taken
    """
    self._deposit(_shares, _receiver)
    return _shares

@external
@view
def maxWithdraw(_owner: address) -> uint256:
    """
    @notice Get the maximum amount of assets an account is allowed to withdraw
    @param _owner Account
    @return Maximum amount the account is allowed to withdraw
    """
    return self.balanceOf[_owner]

@external
@view
def previewWithdraw(_assets: uint256) -> uint256:
    """
    @notice Simulate the effect of a withdrawal
    @param _assets Amount of assets to withdraw
    @return Amount of shares that will be redeemed
    """
    return _assets

@external
def withdraw(_assets: uint256, _receiver: address = msg.sender, _owner: address = msg.sender) -> uint256:
    """
    @notice Withdraw assets
    @param _assets Amount of assets to withdraw
    @param _receiver Account that will receive the assets
    @param _owner Owner of the shares that will be redeemed
    @return Amount of shares redeemed
    """
    self._withdraw(_assets, _receiver, _owner)
    return _assets

@external
@view
def maxRedeem(_owner: address) -> uint256:
    """
    @notice Get the maximum amount of shares an account is allowed to redeem
    @param _owner Account
    @return Maximum amount the account is allowed to redeem
    """
    return self.balanceOf[_owner]

@external
@view
def previewRedeem(_shares: uint256) -> uint256:
    """
    @notice Simulate the effect of a redemption
    @param _shares Amount of shares to redeem
    @return Amount of assets that will be withdrawn
    """
    return _shares

@external
def redeem(_shares: uint256, _receiver: address = msg.sender, _owner: address = msg.sender) -> uint256:
    """
    @notice Redeem shares
    @param _shares Amount of shares to redeem
    @param _receiver Account that will receive the assets
    @param _owner Owner of the shares that will be redeemed
    @return Amount of assets withdrawn
    """
    self._withdraw(_shares, _receiver, _owner)
    return _shares

# external functions

@external
@view
def total_vote_weight() -> uint256:
    """
    @notice Get the total voting weight
    @return Total vote weight
    """
    last: uint256 = self.last_supply
    week: uint256 = last & WEEK_MASK
    last_week: uint256 = block.timestamp / WEEK_LENGTH - 1
    if week > last_week:
        return shift(last, BAL_SHIFT)
    return self.totalSupply

@external
@view
def vote_weight(_account: address) -> uint256:
    """
    @notice Get the voting weight of an account
    @dev Vote weights are always evaluated at the end of last week
    @param _account Account to get the vote weight for
    @return Vote weight
    """
    last: uint256 = self.last_balances[_account]
    week: uint256 = last & WEEK_MASK
    last_week: uint256 = block.timestamp / WEEK_LENGTH - 1
    if week > last_week:
        return shift(last, BAL_SHIFT)
    return self.balanceOf[_account]

@internal
def _deposit(_amount: uint256, _receiver: address):
    """
    @notice Deposit assets and mint shares
    @param _amount Amount of assets deposited
    @param _receiver Receiver of minted shares
    """
    assert _amount > 0
    self._update_last_supply()
    self._update_last(_receiver)

    self.totalSupply += _amount
    self.balanceOf[_receiver] += _amount
    
    assert ERC20(asset).transferFrom(msg.sender, self, _amount, default_return_value=True)
    log Deposit(msg.sender, _receiver, _amount, _amount)
    log Transfer(empty(address), _receiver, _amount)

@internal
def _withdraw(_amount: uint256, _receiver: address, _owner: address):
    """
    @notice Withdraw assets and burn shares
    @param _amount Amount of assets withdrawn
    @param _receiver Receiver of withdrawn assets
    @param _owner Account to burn shares from
    """
    if _owner != msg.sender:
        self.allowance[_owner][msg.sender] -= _amount # dev: allowance
    
    assert _amount > 0
    self._update_last_supply()
    self._update_last(_owner)

    self.totalSupply -= _amount    
    self.balanceOf[_owner] -= _amount

    assert ERC20(asset).transfer(_receiver, _amount, default_return_value=True)
    log Transfer(_owner, empty(address), _amount)
    log Withdraw(msg.sender, _receiver, _owner, _amount, _amount)

@internal
def _update_last_supply():
    """
    @notice Update last supply
    @dev Should be called before applying supply change
    """
    week: uint256 = self.last_supply & WEEK_MASK
    current_week: uint256 = block.timestamp / WEEK_LENGTH
    if current_week > week:
        self.last_supply = self._pack_balance(current_week, self.totalSupply)

@internal
def _update_last(_account: address):
    """
    @notice Update last balance
    @param _account Account to update last balance for
    @dev Should be called before applying balance change
    """
    week: uint256 = self.last_balances[_account] & WEEK_MASK
    current_week: uint256 = block.timestamp / WEEK_LENGTH
    if current_week > week:
        self.last_balances[_account] = self._pack_balance(current_week, self.balanceOf[_account])

@internal
@pure
def _pack_balance(_week: uint256, _bal: uint256) -> uint256:
    """
    @notice Pack last balance into a single word
    @param _week Week number of last change
    @param _bal Last balance
    @return Packed last balance
    """
    assert _week <= WEEK_MASK and _bal <= BAL_MASK
    return _week | shift(_bal, -BAL_SHIFT)
