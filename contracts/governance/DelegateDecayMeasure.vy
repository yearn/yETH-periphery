# @version 0.3.10
"""
@title Vote weight measure with delegation and decay
@author 0xkorin, Yearn Finance
@license GNU AGPLv3
@notice
    Base voting weight equal to the measure at launch.
    Weight decays linearly to zero in the final 24 hours of the epoch.
    Management can delegate voting weight from one account to the other,
    which zeroes out the weight for the origin and adds some weight based on the 
    token balance to the delegate.
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

genesis: public(immutable(uint256))
staking: public(immutable(Staking))
bootstrap: public(immutable(address))
delegated_staking: public(immutable(Measure))
management: public(address)
pending_management: public(address)

delegate_multiplier: public(uint256)
delegator: public(HashMap[address, address]) # account => delegate to
delegated: public(HashMap[address, address]) # account => delegated from

event SetDelegateMultiplier:
    multiplier: uint256

event Delegate:
    account: indexed(address)
    receiver: indexed(address)

event PendingManagement:
    management: indexed(address)

event SetManagement:
    management: indexed(address)

DELEGATE_SCALE: constant(uint256) = 10_000
DAY: constant(uint256) = 24 * 60 * 60
EPOCH_LENGTH: constant(uint256) = 4 * 7 * DAY

@external
def __init__(_genesis: uint256, _staking: address, _bootstrap: address, _delegated_staking: address):
    """
    @notice Constructor
    @param _genesis Genesis time
    @param _staking Staking contract
    @param _bootstrap Bootstrap contract
    @param _delegated_staking Delegated staking contract
    """
    genesis = _genesis
    staking = Staking(_staking)
    delegated_staking = Measure(_delegated_staking)
    bootstrap = _bootstrap
    self.management = msg.sender

@external
@view
def total_vote_weight() -> uint256:
    """
    @notice Get total vote weight
    @return Total vote weight
    @dev
        Care should be taken to use for quorum purposes, as the sum of actual available 
        vote weights will be lower than this due to asymptotical vote weight increase.
    """
    return staking.totalSupply()

@external
@view
def vote_weight(_account: address) -> uint256:
    """
    @notice Get account vote weight
    @param _account Account to get vote weight for
    @return Account vote weight
    """
    weight: uint256 = Bootstrap(bootstrap).deposits(_account)
    if weight > 0:
        deposited: uint256 = Bootstrap(bootstrap).deposited()
        if deposited > 0:
            weight = weight * staking.vote_weight(bootstrap) / deposited
        else:
            weight = 0
    weight += staking.vote_weight(_account)

    delegated: address = self.delegated[_account]
    if delegated != empty(address):
        weight += delegated_staking.vote_weight(delegated) * self.delegate_multiplier / DELEGATE_SCALE

    left: uint256 = EPOCH_LENGTH - ((block.timestamp - genesis) % EPOCH_LENGTH)
    if left <= DAY:
        return weight * left / DAY

    return weight
    
@external
def set_delegate_multiplier(_multiplier: uint256):
    """
    @notice
        Set the delegate multiplier, the value by which delegated 
        voting weight is multipied by.
    @param _multiplier
        Delegate multiplier value. 
        Maximum value is `DELEGATE_SCALE`, which corresponds to one.
    """
    assert msg.sender == self.management
    assert _multiplier <= DELEGATE_SCALE
    self.delegate_multiplier = _multiplier
    log SetDelegateMultiplier(_multiplier)

@external
def delegate(_account: address, _receiver: address):
    """
    @notice Delegate someones voting weight to someone else
    @param _account Account to delegate voting weight from
    @param _receiver Account to delegate voting weight to
    """
    assert msg.sender == self.management

    previous: address = self.delegator[_account]
    if previous != empty(address):
        self.delegated[previous] = empty(address)

    self.delegator[_account] = _receiver
    if _receiver != empty(address):
        assert self.delegated[_receiver] == empty(address)
        self.delegated[_receiver] = _account
    log Delegate(_account, _receiver)

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
