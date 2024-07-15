# @version 0.3.10
"""
@title yETH deposit/withdrawal facility
@author 0xkorin, Yearn Finance
@license GNU AGPLv3
@notice
    Facility to allow permissioned actors to mint and burn yETH
    at a 1:1 rate with ETH. Management can set the maximum amount of yETH
    debt the facility can hold, as well as add and remove from the mint
    and burn whitelists
"""

interface POL:
    def send_native(_receiver: address, _amount: uint256): nonpayable
    def receive_native(): payable

interface Token:
    def mint(_account: address, _value: uint256): nonpayable
    def burn(_account: address, _value: uint256): nonpayable

token: public(immutable(Token))
management: public(address)
pending_management: public(address)
operator: public(address)
pol: public(address)
capacity: public(uint256)
debt: public(uint256) # denominated in yETH
pol_debt: public(uint256) # denominated in ETH
mint_whitelist: public(HashMap[address, bool])
burn_whitelist: public(HashMap[address, bool])

event Mint:
    caller: indexed(address)
    recipient: address
    amount: uint256

event Burn:
    caller: indexed(address)
    recipient: address
    amount: uint256

event FromPol:
    amount: uint256

event ToPol:
    amount: uint256
    debt_repaid: uint256

event SetCapacity:
    capacity: uint256

event SetMintWhitelist:
    minter: address
    whitelisted: bool

event SetBurnWhitelist:
    burner: address
    whitelisted: bool

event SetOperator:
    operator: address

event SetPol:
    pol: address

event PendingManagement:
    management: indexed(address)

event SetManagement:
    management: indexed(address)

@external
def __init__(_token: address, _pol: address):
    """
    @notice Constructor
    @param _token yETH token contract address
    @param _pol POL contract address
    """
    token = Token(_token)
    self.management = msg.sender
    self.operator = msg.sender
    self.pol = _pol

@external
@payable
def __default__():
    """
    @notice Receive ETH
    @dev Can only be called by POL
    """
    assert msg.sender == self.pol

@external
@view
def available() -> (uint256, uint256):
    """
    @notice Available capacity of the facility
    @return Amount of yETH that can be minted, amount of yETH that can be burned
    """
    capacity: uint256 = self.capacity
    return capacity - min(self.debt, capacity), self.balance

@external
@payable
def mint(_recipient: address = msg.sender):
    """
    @notice Mint yETH by sending ETH in a 1:1 ratio
    @param _recipient Recipient of the minted yETH
    @dev Can only be called by addresses on the mint whitelist
    """
    assert msg.value > 0
    assert self.mint_whitelist[msg.sender]
    debt: uint256 = self.debt + msg.value
    assert debt <= self.capacity

    self.debt = debt
    token.mint(_recipient, msg.value)
    log Mint(msg.sender, _recipient, msg.value)

@external
def burn(_amount: uint256, _recipient: address = msg.sender):
    """
    @notice Burn yETH in exchange for receiving ETH in a 1:1 ratio
    @param _amount Amount of yETH to burn
    @param _recipient Recipient of the unlocked ETH
    @dev Can only be called by addresses on the burn whitelist
    """
    assert _amount > 0
    assert self.burn_whitelist[msg.sender]

    self.debt -= _amount
    token.burn(msg.sender, _amount)
    raw_call(_recipient, b"", value=_amount)
    log Burn(msg.sender, _recipient, _amount)

@external
def from_pol(_amount: uint256):
    """
    @notice Move ETH from the POL to the facility
    @param _amount Amount of ETH to move
    @dev Can only be called by the operator
    """
    assert msg.sender == self.operator
    self.pol_debt += _amount
    POL(self.pol).send_native(self, _amount)
    log FromPol(_amount)

@external
def to_pol(_amount: uint256):
    """
    @notice Move ETH from the facility to the POL
    @param _amount Amount of ETH to move
    @dev Can only be called by the operator
    """
    assert msg.sender == self.operator

    # if we have received ETH from the POL in the past, repay it first
    # this makes sure we dont double count ETH and increase the POL debt cap unfairly
    repay: uint256 = min(_amount, self.pol_debt)
    if repay > 0:
        self.pol_debt -= repay
        POL(self.pol).receive_native(value=repay)

    remaining: uint256 = _amount - repay
    if remaining > 0:
        raw_call(self.pol, b"", value=remaining)
    log ToPol(_amount, repay)

@external
def set_capacity(_capacity: uint256):
    """
    @notice Set the maximum ETH capacity of the facility
    @param _capacity Maximum capacity
    @dev Can only be called by management
    """
    assert msg.sender == self.management
    self.capacity = _capacity
    log SetCapacity(_capacity)

@external
def set_mint_whitelist(_account: address, _whitelisted: bool):
    """
    @notice Set mint whitelist status of an account
    @param _account Account to change the whitelist status for
    @param _whitelisted True: add to whitelist, False: remove from whitelist
    @dev Can only be called by management
    """
    assert msg.sender == self.management
    assert _account != empty(address)
    self.mint_whitelist[_account] = _whitelisted
    log SetMintWhitelist(_account, _whitelisted)

@external
def set_burn_whitelist(_account: address, _whitelisted: bool):
    """
    @notice Set burn whitelist status of an account
    @param _account Account to change the whitelist status for
    @param _whitelisted True: add to whitelist, False: remove from whitelist
    @dev Can only be called by management
    """
    assert msg.sender == self.management
    assert _account != empty(address)
    self.burn_whitelist[_account] = _whitelisted
    log SetBurnWhitelist(_account, _whitelisted)

@external
def set_operator(_operator: address):
    """
    @notice Set the operator address
    @param _operator Address of the new operator
    @dev Can only be called by management
    """
    assert msg.sender == self.management
    self.operator = _operator
    log SetOperator(_operator)

@external
def set_pol(_pol: address):
    """
    @notice Set the POL contract address
    @param _pol Address of the new POL
    @dev Can only be called by management
    """
    assert msg.sender == self.management
    assert _pol != empty(address)
    self.pol = _pol
    log SetPol(_pol)

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
