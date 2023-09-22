# @version 0.3.7
"""
@title Inclusion vote
@author 0xkorin, Yearn Finance
@license GNU AGPLv3
"""

interface Measure:
    def total_vote_weight() -> uint256: view
    def vote_weight(_account: address) -> uint256: view

genesis: public(immutable(uint256))
management: public(address)
pending_management: public(address)
whitelister: public(address)
treasury: public(address)
measure: public(address)
latest_finalized_epoch: public(uint256)
num_candidates: public(HashMap[uint256, uint256]) # epoch => number of candidates
candidates: public(HashMap[uint256, address[33]]) # epoch => [candidate]
candidates_map: public(HashMap[uint256, HashMap[address, uint256]]) # epoch => candidate => candidate idx
applications: public(HashMap[address, uint256]) # candidate => last epoch application
rate_providers: public(HashMap[address, address]) # candidate => rate provider

total_votes: public(HashMap[uint256, uint256]) # epoch => total votes
votes: public(HashMap[uint256, uint256[33]]) # epoch => candidate idx => votes
votes_user: public(HashMap[address, HashMap[uint256, uint256]]) # user => epoch => votes
winners: HashMap[uint256, address] # epoch => winner
winners_idx: HashMap[uint256, uint256] # epoch => winner idx
winner_rate_providers: HashMap[uint256, address] # epoch => winner rate provider

initial_application_fee: public(uint256)
subsequent_application_fee: public(uint256)

event SetMeasure:
    measure: indexed(address)

event PendingManagement:
    management: indexed(address)

event SetManagement:
    management: indexed(address)

WEEK: constant(uint256) = 7 * 24 * 60 * 60
EPOCH_LENGTH: constant(uint256) = 4 * WEEK
VOTE_LENGTH: constant(uint256) = WEEK
VOTE_START: constant(uint256) = EPOCH_LENGTH - VOTE_LENGTH
VOTE_SCALE: constant(uint256) = 10_000
APPLICATION_DISABLED: constant(address) = 0x0000000000000000000000000000000000000001

@external
def __init__(_genesis: uint256, _measure: address):
    assert _genesis <= block.timestamp

    genesis = _genesis
    self.management = msg.sender
    self.whitelister = msg.sender
    self.measure = _measure
    self.treasury = msg.sender
    
    epoch: uint256 = self._epoch()
    assert epoch > 0
    self.latest_finalized_epoch = epoch - 1

    log SetManagement(msg.sender)
    log SetMeasure(_measure)

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
def vote_open() -> bool:
    return self._vote_open()

@internal
@view
def _vote_open() -> bool:
    return (block.timestamp - genesis) % EPOCH_LENGTH >= VOTE_START

@external
@payable
def apply(_token: address):
    epoch: uint256 = self._epoch()
    assert self.latest_finalized_epoch == epoch - 1
    assert self.num_candidates[epoch] < 32
    assert not self._vote_open()

    fee: uint256 = 0
    application_epoch: uint256 = self.applications[_token]
    assert epoch > application_epoch, "already applied"
    self.applications[_token] = epoch

    if application_epoch == 0:
        fee = self.initial_application_fee
    else:
        fee = self.subsequent_application_fee
    assert msg.value == fee

    provider: address = self.rate_providers[_token]
    assert provider != APPLICATION_DISABLED
    if provider != empty(address):
        self._whitelist(epoch, _token)

@internal
def _whitelist(_epoch: uint256, _token: address):
    n: uint256 = self.num_candidates[_epoch] + 1
    self.num_candidates[_epoch] = n
    self.candidates[_epoch][n] = _token
    self.candidates_map[_epoch][_token] = n

@external
def vote(_votes: DynArray[uint256, 33]):
    epoch: uint256 = self._epoch()
    assert self._vote_open()
    assert self.votes_user[msg.sender][epoch] == 0

    n: uint256 = self.num_candidates[epoch] + 1
    assert len(_votes) <= n

    weight: uint256 = Measure(self.measure).vote_weight(msg.sender)
    assert weight > 0
    self.total_votes[epoch] += weight
    self.votes_user[msg.sender][epoch] = weight

    total: uint256 = 0
    for i in range(33):
        if i == len(_votes):
            break
        if _votes[i] == 0:
            continue

        votes: uint256 = _votes[i] * weight / VOTE_SCALE
        self.votes[epoch][i] += votes
        
        total += _votes[i]

    assert total == VOTE_SCALE

@external
def finalize_epoch():
    epoch: uint256 = self.latest_finalized_epoch + 1
    if epoch >= self._epoch():
        return

    n: uint256 = self.num_candidates[epoch] + 1
    winner: address = empty(address)
    winner_votes: uint256 = 0
    for i in range(33):
        if i == n:
            break
        votes: uint256 = self.votes[epoch][i]
        if votes > winner_votes:
            candidate: address = self.candidates[epoch][i]
            if self.rate_providers[candidate] in [empty(address), APPLICATION_DISABLED]:
                continue
            winner = candidate
            winner_votes = votes

    self.winners[epoch] = winner
    self.winner_rate_providers[epoch] = self.rate_providers[winner]
    self.rate_providers[winner] = APPLICATION_DISABLED
    self.latest_finalized_epoch = epoch

@external
def set_rate_provider(_token: address, _provider: address):
    assert msg.sender == self.whitelister
    self.rate_providers[_token] = _provider

    epoch: uint256 = self._epoch()
    if _provider not in [empty(address), APPLICATION_DISABLED] and \
        self.applications[_token] == epoch and self.num_candidates[epoch] < 32 and \
        self.candidates_map[epoch][_token] > 0:
        # whitelist token for vote if it has an application for this epoch
        self._whitelist(epoch, _token)

@external
def sweep(_recipient: address):
    assert msg.sender == self.treasury
    assert self.balance > 0
    raw_call(_recipient, b"", value=self.balance)

@external
def set_whitelister(_whitelister: address):
    assert msg.sender == self.management
    self.whitelister = _whitelister

@external
def set_treasury(_treasury: address):
    assert msg.sender == self.management
    self.treasury = _treasury

@external
def set_measure(_measure: address):
    assert msg.sender == self.management
    assert _measure != empty(address)
    assert not self._vote_open()
    self.measure = _measure
    log SetMeasure(_measure)

@external
def set_application_fees(_initial: uint256, _subsequent: uint256):
    assert msg.sender == self.management
    self.initial_application_fee = _initial
    self.subsequent_application_fee = _subsequent

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
