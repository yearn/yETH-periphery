# @version 0.3.7
"""
@title Generic governor
@author 0xkorin, Yearn Finance
@license GNU AGPLv3
"""

interface Measure:
    def total_vote_weight() -> uint256: view
    def vote_weight(_account: address) -> uint256: view

interface Executor:
    def execute(_script: Bytes[65536]): nonpayable

struct Proposal:
    epoch: uint256
    author: address
    state: uint256
    hash: bytes32
    yea: uint256
    nay: uint256

genesis: public(immutable(uint256))

management: public(address)
pending_management: public(address)

measure: public(address)
executor: public(address)
delay: public(uint256)
majority: public(uint256)
propose_min_weight: public(uint256)

num_proposals: public(uint256)
proposals: public(HashMap[uint256, Proposal])
voted: public(HashMap[address, HashMap[uint256, bool]])

event PendingManagement:
    management: indexed(address)

event SetManagement:
    management: indexed(address)

STATE_ABSENT: constant(uint256)    = 0
STATE_PROPOSED: constant(uint256)  = 1
STATE_PASSED: constant(uint256)    = 2
STATE_REJECTED: constant(uint256)  = 3
STATE_RETRACTED: constant(uint256) = 4
STATE_CANCELLED: constant(uint256) = 5
STATE_ENACTED: constant(uint256)   = 6

WEEK: constant(uint256) = 7 * 24 * 60 * 60
EPOCH_LENGTH: constant(uint256) = 4 * WEEK
VOTE_LENGTH: constant(uint256) = WEEK
VOTE_START: constant(uint256) = EPOCH_LENGTH - VOTE_LENGTH
VOTE_SCALE: constant(uint256) = 10_000

@external
def __init__(_genesis: uint256, _measure: address, _executor: address):
    assert _genesis <= block.timestamp
    assert _measure != empty(address)
    assert _executor != empty(address)

    genesis = _genesis
    self.management = msg.sender
    self.measure = _measure
    self.executor = _executor

@external
@view
def epoch() -> uint256:
    return self._epoch()

@internal
@view
def _epoch() -> uint256:
    return (block.timestamp - genesis) / EPOCH_LENGTH

@external
@view
def propose_open() -> bool:
    return self._propose_open()

@internal
@view
def _propose_open() -> bool:
    return (block.timestamp - genesis) % EPOCH_LENGTH < VOTE_START

@external
@view
def vote_open() -> bool:
    return self._vote_open()

@internal
@view
def _vote_open() -> bool:
    return (block.timestamp - genesis) % EPOCH_LENGTH >= VOTE_START

@external
@view
def proposal_state(_idx: uint256) -> uint256:
    return self._proposal_state(_idx)

@external
def update_proposal_state(_idx: uint256) -> uint256:
    state: uint256 = self._proposal_state(_idx)
    if state != STATE_ABSENT:
        self.proposals[_idx].state = state
    return state

@internal
@view
def _proposal_state(_idx: uint256) -> uint256:
    state: uint256 = self.proposals[_idx].state
    if state != STATE_PROPOSED:
        return state

    current_epoch: uint256 = self._epoch()
    vote_epoch: uint256 = self.proposals[_idx].epoch
    if current_epoch == vote_epoch:
        return STATE_PROPOSED
    
    if current_epoch == vote_epoch + 1:
        yea: uint256 = self.proposals[_idx].yea
        nay: uint256 = self.proposals[_idx].nay
        votes: uint256 = yea + nay
        if votes > 0 and yea * VOTE_SCALE / votes >= self.majority:
            return STATE_PASSED

    return STATE_REJECTED

@external
def propose(_script: Bytes[65536]) -> uint256:
    assert self._propose_open()
    assert Measure(self.measure).vote_weight(msg.sender) >= self.propose_min_weight

    idx: uint256 = self.num_proposals
    hash: bytes32 = keccak256(_script)
    self.num_proposals = idx + 1
    self.proposals[idx].epoch = self._epoch()
    self.proposals[idx].author = msg.sender
    self.proposals[idx].state = STATE_PROPOSED
    self.proposals[idx].hash = hash
    return idx

@external
def retract(_idx: uint256):
    assert msg.sender == self.proposals[_idx].author
    state: uint256 = self._proposal_state(_idx)
    assert state == STATE_PROPOSED or state == STATE_PASSED
    self.proposals[_idx].state = STATE_RETRACTED

@external
def cancel(_idx: uint256):
    assert msg.sender == self.management
    state: uint256 = self._proposal_state(_idx)
    assert state == STATE_PROPOSED or state == STATE_PASSED
    self.proposals[_idx].state = STATE_CANCELLED

@external
def vote_yea(_idx: uint256):
    self._vote(_idx, VOTE_SCALE, 0)

@external
def vote_nay(_idx: uint256):
    self._vote(_idx, 0, VOTE_SCALE)

@external
def vote(_idx: uint256, _yea: uint256, _nay: uint256):
    self._vote(_idx, _yea, _nay)

@internal
def _vote(_idx: uint256, _yea: uint256, _nay: uint256):
    assert self._vote_open()
    assert self.proposals[_idx].epoch == self._epoch()
    assert self.proposals[_idx].state == STATE_PROPOSED
    assert not self.voted[msg.sender][_idx]
    assert _yea + _nay == VOTE_SCALE

    weight: uint256 = Measure(self.measure).vote_weight(msg.sender)
    self.voted[msg.sender][_idx] = True
    if _yea > 0:
        self.proposals[_idx].yea += weight * _yea / VOTE_SCALE
    if _nay > 0:
        self.proposals[_idx].nay += weight * _nay / VOTE_SCALE

@external
def execute(_idx: uint256, _script: Bytes[65536]):
    assert self._proposal_state(_idx) == STATE_PASSED
    assert keccak256(_script) == self.proposals[_idx].hash
    assert (block.timestamp - genesis) % EPOCH_LENGTH >= self.delay

    self.proposals[_idx].state = STATE_ENACTED
    Executor(self.executor).execute(_script)

@external
def set_measure(_measure: address):
    assert msg.sender == self.management
    assert _measure != empty(address)
    self.measure = _measure

@external
def set_executor(_executor: address):
    assert msg.sender == self.management
    assert _executor != empty(address)
    self.executor = _executor

@external
def set_delay(_delay: uint256):
    assert msg.sender == self.management
    assert _delay <= VOTE_START
    self.delay = _delay

@external
def set_majority(_majority: uint256):
    assert msg.sender == self.management
    assert _majority <= VOTE_SCALE
    self.majority = _majority

@external
def set_propose_min_weight(_propose_min_weight: uint256):
    assert msg.sender == self.management
    self.propose_min_weight = _propose_min_weight

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
