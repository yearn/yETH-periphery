# @version 0.3.7
"""
@title Vote weight measure with delegation
@author 0xkorin, Yearn Finance
@license GNU AGPLv3
"""

interface Measure:
    def total_vote_weight() -> uint256: view
    def vote_weight(_account: address) -> uint256: view
implements: Measure

interface Staking:
    def totalSupply() -> uint256: view
    def balanceOf(_account: address) -> uint256: view
    def vote_weight(_account: address) -> uint256: view

interface Bootstrap:
    def deposited() -> uint256: view
    def deposits(_account: address) -> uint256: view

staking: public(immutable(address))
bootstrap: public(immutable(address))
management: public(address)
pending_management: public(address)

delegate_multiplier: public(uint256)
delegator: public(HashMap[address, address]) # account => delegate to
delegated: public(HashMap[address, address]) # account => delegated from

event PendingManagement:
    management: indexed(address)

event SetManagement:
    management: indexed(address)

DELEGATE_SCALE: constant(uint256) = 10_000

@external
def __init__(_staking: address, _bootstrap: address):
    """
    @notice Constructor
    @param _staking Staking contract
    @param _bootstrap Bootstrap contract
    """
    staking = _staking
    bootstrap = _bootstrap
    self.management = msg.sender

@external
@view
def total_vote_weight() -> uint256:
    """
    @notice Get total vote weight
    @return Total vote weight
    @dev
        Equal to sum of all vote weights at T=inf.
        Care should be taken to use for quorum purposes, as the sum of actual available 
        vote weights will be lower than this due to asymptotical vote weight increase.
    """
    return Staking(staking).totalSupply()

@external
@view
def vote_weight(_account: address) -> uint256:
    """
    @notice Get account vote weight
    @param _account Account to get vote weight for
    @return Account vote weight
    """
    if self.delegator[_account] != empty(address) and self.delegate_multiplier > 0:
        return 0

    weight: uint256 = Bootstrap(bootstrap).deposits(_account)
    if weight > 0:
        deposited: uint256 = Bootstrap(bootstrap).deposited()
        if deposited > 0:
            weight = weight * Staking(staking).vote_weight(bootstrap) / deposited
        else:
            weight = 0
    weight += Staking(staking).vote_weight(_account)

    delegated: address = self.delegated[_account]
    if delegated != empty(address):
        weight += Staking(staking).balanceOf(delegated) * self.delegate_multiplier / DELEGATE_SCALE

    return weight
    
@external
def set_delegate_multiplier(_multiplier: uint256):
    assert msg.sender == self.management
    assert _multiplier <= DELEGATE_SCALE
    self.delegate_multiplier = _multiplier

@external
def delegate(_account: address, _receiver: address):
    assert msg.sender == self.management

    previous: address = self.delegator[_account]
    if previous != empty(address):
        self.delegated[previous] = empty(address)

    self.delegator[_account] = _receiver
    if _receiver != empty(address):
        assert self.delegated[_receiver] == empty(address)
        self.delegated[_receiver] = _account

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
