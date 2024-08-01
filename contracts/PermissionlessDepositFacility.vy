# @version 0.3.10
"""
@title Permissionless yETH deposit/withdrawal facility
@author 0xkorin, Yearn Finance
@license GNU AGPLv3
@notice
    Facility to allow anyone to mint and burn yETH 
    in exchange for ETH, at a fee
"""

from vyper.interfaces import ERC20
from vyper.interfaces import ERC4626

interface Facility:
    def available() -> (uint256, uint256): view
    def mint(_recipient: address): payable
    def burn(_amount: uint256): nonpayable

token: public(immutable(address))
staking: public(immutable(ERC4626))
facility: public(immutable(Facility))

management: public(address)
pending_management: public(address)

treasury: public(address)
packed_fee_rates: public(uint256)

event Deposit:
    account: indexed(address)
    recipient: address
    amount_in: uint256
    amount_out: uint256
    stake: bool

event Withdraw:
    account: indexed(address)
    recipient: address
    amount_in: uint256
    amount_out: uint256

event ClaimFees:
    amount: uint256

event SetFeeRates:
    deposit_fee_rate: uint256
    withdraw_fee_rate: uint256

event SetStrategy:
    strategy: address

event SetTreasury:
    treasury: address

event PendingManagement:
    management: indexed(address)

event SetManagement:
    management: indexed(address)

FEE_RATE_SCALE: constant(uint256) = 10_000
MAX_FEE_RATE: constant(uint256) = FEE_RATE_SCALE / 100
MASK: constant(uint256) = (1 << 128) - 1

@external
def __init__(_token: address, _staking: address, _facility: address):
    """
    @notice Constructor
    @param _token yETH token contract address
    @param _staking st-yETH token contract address
    @param _facility ETH deposit facility address
    """
    token = _token
    staking = ERC4626(_staking)
    facility = Facility(_facility)
    self.management = msg.sender
    self.treasury = msg.sender

    assert ERC20(token).approve(_staking, max_value(uint256), default_return_value=True)

@external
@payable
def __default__():
    """
    @notice Receive ETH
    """
    if msg.sender == facility.address:
        return
    self._deposit(False, msg.sender)

@external
@view
def available() -> (uint256, uint256):
    """
    @notice Available capacity of the facility
    @return Amount of yETH that can be minted, amount of yETH that can be burned
    """
    return facility.available()

@external
@payable
def deposit(_stake: bool = True, _recipient: address = msg.sender) -> uint256:
    """
    @notice Deposit ETH and mint yETH
    @param _stake True: stake the minted into st-yETH
    @param _recipient Recipient of (st-)yETH
    @return Amount of (st-)yETH minted
    """
    return self._deposit(_stake, _recipient)
    
@internal
@payable
@nonreentrant("lock")
def _deposit(_stake: bool, _recipient: address) -> uint256:
    """
    @notice Deposit ETH and mint yETH
    """
    amount: uint256 = msg.value

    deposit_fee: uint256 = self.packed_fee_rates >> 128
    if deposit_fee > 0:
        deposit_fee = amount * deposit_fee / FEE_RATE_SCALE
        amount -= deposit_fee

    recipient: address = _recipient
    if _stake:
        recipient = self
    facility.mint(recipient, value=amount)

    if _stake:
        amount = staking.deposit(amount, _recipient)

    log Deposit(msg.sender, _recipient, msg.value, amount, _stake)
    return amount

@external
@nonreentrant("lock")
def withdraw(_amount: uint256, _recipient: address = msg.sender) -> uint256:
    """
    @notice Withdraw ETH and burn yETH
    @param _amount Amount of yETH to burn
    @param _recipient Recipient of the withdrawn ETH
    @return Amount of WETH withdrawn
    @dev Can only be called by the strategy
    """
    assert _amount > 0

    amount: uint256 = _amount
    assert ERC20(token).transferFrom(msg.sender, self, amount, default_return_value=True)
    facility.burn(amount)

    withdraw_fee: uint256 = self.packed_fee_rates & MASK
    if withdraw_fee > 0:
        withdraw_fee = amount * withdraw_fee / FEE_RATE_SCALE
        amount -= withdraw_fee

    raw_call(_recipient, b"", value=amount)

    log Withdraw(msg.sender, _recipient, _amount, amount)
    return amount

@external
@view
def fee_rates() -> (uint256, uint256):
    """
    @notice Get deposit and withdraw fee rates
    @return Deposit fee rate (bps), withdraw fee rate (bps)
    """
    packed_fee_rates: uint256 = self.packed_fee_rates
    return packed_fee_rates >> 128, packed_fee_rates & MASK

@external
@view
def pending_fees() -> uint256:
    """
    @notice Get the amount of fees that can be sent to the treasury
    """
    return self.balance

@external
def claim_fees() -> uint256:
    """
    @notice Claim the pending fees by sending them to the treasury
    @return Amount of fees claimed
    """
    fees: uint256 = self.balance
    assert fees > 0
    raw_call(self.treasury, b"", value=fees)
    log ClaimFees(fees)
    return fees

@external
def set_fee_rates(_deposit_fee_rate: uint256, _withdraw_fee_rate: uint256):
    """
    @notice Set deposit and withdraw fee rates
    @param _deposit_fee_rate Deposit fee rate (bps)
    @param _withdraw_fee_rate Withdraw fee rate (bps)
    @dev Can only be called by management
    """
    assert msg.sender == self.management
    assert _deposit_fee_rate <= MAX_FEE_RATE and _withdraw_fee_rate <= MAX_FEE_RATE
    self.packed_fee_rates = (_deposit_fee_rate << 128) | _withdraw_fee_rate
    log SetFeeRates(_deposit_fee_rate, _withdraw_fee_rate)

@external
def set_treasury(_treasury: address):
    """
    @notice Set treasury address
    @param _treasury Treasury address
    @dev Can only be called by management
    """
    assert msg.sender == self.management
    assert _treasury != empty(address)
    self.treasury = _treasury
    log SetTreasury(_treasury)

@external
def set_management(_management: address):
    """
    @notice 
        Set the pending management address.
        Needs to be accepted by that account separately to transfer management over
    @param _management New pending management address
    """
    assert msg.sender == self.management
    self.pending_management = _management
    log PendingManagement(_management)

@external
def accept_management():
    """
    @notice 
        Accept management role.
        Can only be called by account previously marked as pending management by current management
    """
    assert msg.sender == self.pending_management
    self.pending_management = empty(address)
    self.management = msg.sender
    log SetManagement(msg.sender)
