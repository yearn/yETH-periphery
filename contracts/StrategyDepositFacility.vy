# @version 0.3.10
"""
@title yETH strategy deposit/withdrawal facility
@author 0xkorin, Yearn Finance
@license GNU AGPLv3
@notice
    Facility to allow the v3 strategy to mint and burn yETH 
    in exchange for WETH
"""

from vyper.interfaces import ERC20
from vyper.interfaces import ERC4626

interface WETH:
    def deposit(): payable
    def withdraw(_amount: uint256): nonpayable

interface Facility:
    def available() -> (uint256, uint256): view
    def mint(_recipient: address): payable
    def burn(_amount: uint256): nonpayable

token: public(immutable(address))
staking: public(immutable(ERC4626))
facility: public(immutable(Facility))
weth: public(immutable(WETH))

management: public(address)
pending_management: public(address)

treasury: public(address)
strategy: public(address)
packed_fee_rates: public(uint256)

event Deposit:
    amount_in: uint256
    amount_out: uint256
    stake: bool

event Withdraw:
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
def __init__(_token: address, _staking: address, _facility: address, _weth: address):
    """
    @notice Constructor
    @param _token yETH token contract address
    @param _staking st-yETH token contract address
    @param _facility ETH deposit facility address
    @param _weth Wrapped ETH contract address
    """
    token = _token
    staking = ERC4626(_staking)
    facility = Facility(_facility)
    weth = WETH(_weth)
    self.management = msg.sender
    self.treasury = msg.sender

    assert ERC20(token).approve(_staking, max_value(uint256), default_return_value=True)

@external
@payable
def __default__():
    """
    @notice Receive ETH
    @dev Can only be called by the WETH contract and the ETH facility
    """
    assert msg.sender in [weth.address, facility.address]

@external
@view
def available() -> (uint256, uint256):
    """
    @notice Available capacity of the facility
    @return Amount of yETH that can be minted, amount of yETH that can be burned
    """
    return facility.available()

@external
def deposit(_amount: uint256, _stake: bool) -> uint256:
    """
    @notice Deposit WETH and mint yETH
    @param _amount Amount of WETH to transfer in
    @param _stake True: stake the minted into st-yETH
    @return Amount of (st-)yETH minted
    @dev Can only be called by the strategy
    """
    assert msg.sender == self.strategy

    recipient: address = msg.sender
    if _stake:
        recipient = self
    amount: uint256 = _amount

    assert ERC20(weth.address).transferFrom(msg.sender, self, amount, default_return_value=True)
    weth.withdraw(amount)

    deposit_fee: uint256 = self.packed_fee_rates >> 128
    if deposit_fee > 0:
        deposit_fee = amount * deposit_fee / FEE_RATE_SCALE
        amount -= deposit_fee

    facility.mint(recipient, value=amount)
    if _stake:
        amount = staking.deposit(amount, msg.sender)

    log Deposit(_amount, amount, _stake)
    return amount

@external
def withdraw(_amount: uint256) -> uint256:
    """
    @notice Withdraw WETH and burn yETH
    @param _amount Amount of yETH to burn
    @return Amount of WETH withdrawn
    @dev Can only be called by the strategy
    """
    assert msg.sender == self.strategy

    amount: uint256 = _amount
    assert ERC20(token).transferFrom(msg.sender, self, amount, default_return_value=True)
    facility.burn(amount)

    withdraw_fee: uint256 = self.packed_fee_rates & MASK
    if withdraw_fee > 0:
        withdraw_fee = amount * withdraw_fee / FEE_RATE_SCALE
        amount -= withdraw_fee

    weth.deposit(value=amount)
    assert ERC20(weth.address).transfer(msg.sender, amount, default_return_value=True)

    log Withdraw(_amount, amount)
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
def set_strategy(_strategy: address):
    """
    @notice Set yETH strategy address
    @param _strategy Strategy address
    @dev Can only be called by management
    """
    assert msg.sender == self.management
    self.strategy = _strategy
    log SetStrategy(_strategy)

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
