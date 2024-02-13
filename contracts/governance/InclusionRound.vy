# @version 0.3.7
"""
@title Inclusion round
@author 0xkorin, Yearn Finance
@license GNU AGPLv3
@notice
    Governor that enables inclusion voting in a specific round
"""

from vyper.interfaces import ERC20

interface Vote:
    def enabled() -> bool: view
    def applications(_token: address) -> uint256: view
    def application_fee(_token: address) -> uint256: view
    def apply(_token: address): nonpayable

interface Executor:
    def execute_single(_to: address, _data: Bytes[2048]): nonpayable

genesis: public(immutable(uint256))
executor: public(immutable(Executor))
vote: public(immutable(address))
management: public(address)
pending_management: public(address)
vote_epoch: public(uint256)

event SetVoteEpoch:
    epoch: uint256

event PendingManagement:
    management: indexed(address)

event SetManagement:
    management: indexed(address)

EPOCH_LENGTH: constant(uint256) = 4 * 7 * 24 * 60 * 60

@external
def __init__(_genesis: uint256, _executor: address, _vote: address):
    """
    @notice Constructor
    @param _genesis Genesis timestamp
    @param _executor Executor contract address
    @param _vote Inclusion vote contract address
    """
    genesis = _genesis
    executor = Executor(_executor)
    vote = _vote
    self.management = msg.sender

@external
@view
def epoch() -> uint256:
    """
    @notice Get the current epoch
    @return Current epoch
    """
    return self._epoch()

@internal
@view
def _epoch() -> uint256:
    """
    @notice Get the current epoch
    """
    return (block.timestamp - genesis) / EPOCH_LENGTH

@external
def toggle():
    """
    @notice Toggle the status of the inclusion vote contract
    """
    enabled: bool = self._epoch() == self.vote_epoch
    if enabled == Vote(vote).enabled():
        return

    data: Bytes[4] = b""
    if enabled:
        data = method_id('enable()')
    else:
        data = method_id('disable()')
    executor.execute_single(vote, data)

@external
def set_vote_epoch(_epoch: uint256):
    """
    @notice Set the next epoch where inclusion voting will be enabled
    @param _epoch Epoch number
    """
    assert msg.sender == self.management
    assert _epoch >= self._epoch()
    self.vote_epoch = _epoch
    log SetVoteEpoch(_epoch)

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
