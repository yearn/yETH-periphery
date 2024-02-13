# @version 0.3.7
"""
@title Inclusion vote
@author 0xkorin, Yearn Finance
@license GNU AGPLv3
@notice
    Voting contract for inclusion into the pool.
    Time is divided in 4 week epochs. During the first three weeks, any user
    can submit an application on behalf of a token. A fee is potentially charged
    as an anti spam measure.

    The operator of this contract is tasked with deploying a rate provider for 
    protocols that have applied. A protocol that has a rate provider and an application
    is automatically whitelisted for the vote of the current epoch.

    In the final week of the epoch, all users are able to vote on the whitelisted candidates,
    as well as a 'blank' option, indicating their opposition to all of the candidates.
    The candidate, if any, with the most amount of votes will be whitelisted by the pool governor.
"""

from vyper.interfaces import ERC20

interface Measure:
    def vote_weight(_account: address) -> uint256: view

genesis: public(immutable(uint256))
management: public(address)
pending_management: public(address)
operator: public(address)
treasury: public(address)
measure: public(address)
enabled: public(bool)
latest_finalized_epoch: public(uint256)
num_candidates: public(HashMap[uint256, uint256]) # epoch => number of candidates
candidates: public(HashMap[uint256, address[33]]) # epoch => [candidate]
candidates_map: public(HashMap[uint256, HashMap[address, uint256]]) # epoch => candidate => candidate idx
applications: public(HashMap[address, uint256]) # candidate => last epoch application
rate_providers: public(HashMap[address, address]) # candidate => rate provider

total_votes: public(HashMap[uint256, uint256]) # epoch => total votes
votes: public(HashMap[uint256, uint256[33]]) # epoch => candidate idx => votes
votes_user: public(HashMap[address, HashMap[uint256, uint256]]) # user => epoch => votes
winners: public(HashMap[uint256, address]) # epoch => winner
winner_rate_providers: public(HashMap[uint256, address]) # epoch => winner rate provider

fee_token: public(address)
initial_fee: public(uint256)
subsequent_fee: public(uint256)

event Apply:
    epoch: indexed(uint256)
    token: indexed(address)
    account: address

event Whitelist:
    epoch: indexed(uint256)
    token: indexed(address)
    idx: uint256

event Vote:
    epoch: indexed(uint256)
    account: indexed(address)
    weight: uint256
    votes: DynArray[uint256, 33]

event Finalize:
    epoch: indexed(uint256)
    winner: indexed(address)

event SetRateProvider:
    token: indexed(address)
    provider: address

event Enable:
    enabled: bool

event SetOperator:
    operator: indexed(address)

event SetTreasury:
    treasury: indexed(address)

event SetFeeToken:
    fee_token: indexed(address)

event SetFees:
    initial: uint256
    subsequent: uint256

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
def __init__(_genesis: uint256, _measure: address, _fee_token: address):
    """
    @notice Constructor
    @param _genesis Timestamp of start of epoch 0
    @param _measure Vote weight measure
    @param _fee_token Application fee token
    """
    assert _genesis <= block.timestamp
    genesis = _genesis
    self.management = msg.sender
    self.operator = msg.sender
    self.treasury = msg.sender
    self.measure = _measure
    self.enabled = True
    self.fee_token = _fee_token
    
    epoch: uint256 = self._epoch()
    assert epoch > 0
    self.latest_finalized_epoch = epoch - 1

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
@view
def apply_open() -> bool:
    """
    @notice Query whether the application period is currently open
    @return True: application period is open, False: application period is closed
    """
    return not self._vote_open()

@external
@view
def vote_open() -> bool:
    """
    @notice Query whether the vote period is currently open
    @return True: vote period is open, False: vote period is closed
    """
    return self._vote_open()

@internal
@view
def _vote_open() -> bool:
    """
    @notice Query whether the vote period is currently open
    """
    return (block.timestamp - genesis) % EPOCH_LENGTH >= VOTE_START

@external
@view
def has_applied(_token: address) -> bool:
    """
    @notice Query whether a token has applied in the current epoch
    @param _token Token address to query for
    @return True: token has applied this epoch, False: token has not applied this epoch
    """
    if not self.enabled:
        return self.applications[_token] == max_value(uint256)
    return self.applications[_token] == self._epoch()

@external
@view
def application_fee(_token: address) -> uint256:
    """
    @notice Get the application fee for a specific token
    @param _token Token address to get fee for
    @return Application fee
    """
    assert self.rate_providers[_token] != APPLICATION_DISABLED
    if self.applications[_token] == 0:
        return self.initial_fee
    return self.subsequent_fee

@external
def apply(_token: address):
    """
    @notice
        Apply for a token to be included into the pool. Each token can only apply once per epoch.
        Included assets can no longer apply to be included.
        Charges a fee, dependent on whether the application is the first one 
        or a follow up in a subsequent epoch.
        If the token already has a rate provider configured, it will be automatically whitelisted
        for the voting procedure.
    @param _token Token address to apply for
    """
    epoch: uint256 = self._epoch()
    enabled: bool = self.enabled
    assert self.latest_finalized_epoch == epoch - 1
    assert not self._vote_open() or not enabled
    
    if enabled:
        assert self.num_candidates[epoch] < 32
    else:
        epoch = max_value(uint256)

    application_epoch: uint256 = self.applications[_token]
    assert epoch > application_epoch, "already applied"
    self.applications[_token] = epoch

    provider: address = self.rate_providers[_token]
    assert provider != APPLICATION_DISABLED
    if provider != empty(address) and enabled:
        self._whitelist(epoch, _token)

    fee: uint256 = 0
    if application_epoch == 0:
        fee = self.initial_fee
    else:
        fee = self.subsequent_fee
    if fee > 0:
        assert ERC20(self.fee_token).transferFrom(msg.sender, self, fee, default_return_value=True)
    log Apply(epoch, _token, msg.sender)

@external
def whitelist(_tokens: DynArray[address, 32]):
    """
    @notice Whitelist tokens that applied while the contract was disabled
    @param _tokens Array of tokens to whitelist
    @dev Can be called by anyone
    """
    epoch: uint256 = self._epoch()
    assert self.enabled
    assert not self._vote_open()
    for token in _tokens:
        assert self.num_candidates[epoch] < 32
        assert self.applications[token] == max_value(uint256)
        assert self.rate_providers[token] not in [empty(address), APPLICATION_DISABLED]
        self.applications[token] = epoch
        self._whitelist(epoch, token)

@internal
def _whitelist(_epoch: uint256, _token: address):
    """
    @notice Whitelist a token, assumes all preconditions are met
    """
    n: uint256 = self.num_candidates[_epoch] + 1
    self.num_candidates[_epoch] = n
    self.candidates[_epoch][n] = _token
    self.candidates_map[_epoch][_token] = n
    log Whitelist(_epoch, _token, n)

@external
def vote(_votes: DynArray[uint256, 33]):
    """
    @notice
        Vote for preferred candidates. The first entry corresponds to a 'blank' vote,
        meaning no new asset is to be added to the pool.
        Votes are in basispoints and must add to 100%
    @param _votes List of votes in bps
    """
    epoch: uint256 = self._epoch()
    assert self._vote_open()
    assert self.votes_user[msg.sender][epoch] == 0
    assert self.enabled

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
    log Vote(epoch, msg.sender, weight, _votes)

@external
def finalize_epoch():
    """
    @notice Finalize an epoch, if possible. Will determine the winner of the vote after epoch has ended
    """
    epoch: uint256 = self.latest_finalized_epoch + 1
    if epoch >= self._epoch():
        # nothing to finalize
        return

    # find candidate with most votes
    n: uint256 = self.num_candidates[epoch] + 1
    winner: address = empty(address)
    winner_votes: uint256 = 0
    for i in range(33):
        if i == n:
            break
        votes: uint256 = self.votes[epoch][i]
        if votes > winner_votes:
            candidate: address = self.candidates[epoch][i]
            if candidate != empty(address) and self.rate_providers[candidate] in [empty(address), APPLICATION_DISABLED]:
                # operator could have unset rate provider after
                continue
            winner = candidate
            winner_votes = votes

    self.winners[epoch] = winner
    if winner != empty(address):
        self.winner_rate_providers[epoch] = self.rate_providers[winner]
        self.rate_providers[winner] = APPLICATION_DISABLED
    self.latest_finalized_epoch = epoch
    log Finalize(epoch, winner)

@external
def set_rate_provider(_token: address, _provider: address):
    """
    @notice
        Set a rate provider of a token. Will automatically whitelist the token
        for the vote if there already is an application in this epoch.
    @param _token Candidate token to set rate provider for
    @param _provider Rate provider address
    """
    epoch: uint256 = self._epoch()
    assert msg.sender == self.operator
    assert (not self._vote_open() and self.latest_finalized_epoch + 1 == epoch) or \
        _provider == empty(address)
    self.rate_providers[_token] = _provider
    log SetRateProvider(_token, _provider)

    if _provider not in [empty(address), APPLICATION_DISABLED] and \
        self.applications[_token] == epoch and self.num_candidates[epoch] < 32 and \
        self.candidates_map[epoch][_token] == 0:
        # whitelist token for vote if it has an application for this epoch
        self._whitelist(epoch, _token)

@external
def sweep(_token: address, _recipient: address = msg.sender):
    """
    @notice Sweep application fees and other tokens from this contract
    @param _token Token to sweep
    @param _recipient Recipient of the swept tokens
    """
    assert msg.sender == self.treasury
    amount: uint256 = ERC20(_token).balanceOf(self)
    if amount > 0:
        assert ERC20(_token).transfer(_recipient, amount, default_return_value=True)

@external
def set_operator(_operator: address):
    """
    @notice Set the operator. The operator is responsible for setting rate providers for the applicants
    @param _operator New operator address
    """
    assert msg.sender == self.management or msg.sender == self.operator
    self.operator = _operator
    log SetOperator(_operator)

@external
def set_treasury(_treasury: address):
    """
    @notice Set the treasury. The treasury can sweep (application fee) tokens
    @param _treasury New treasury address
    """
    assert msg.sender == self.treasury
    self.treasury = _treasury
    log SetTreasury(_treasury)

@external
def set_measure(_measure: address):
    """
    @notice Set vote weight measure contract
    @param _measure New vote weight measure
    """
    assert msg.sender == self.management
    assert _measure != empty(address)
    assert not self._vote_open()
    self.measure = _measure
    log SetMeasure(_measure)

@external
def enable():
    """
    @notice Enable the inclusion vote procedure
    """
    assert msg.sender == self.management
    assert not self._vote_open()
    self.enabled = True
    log Enable(True)

@external
def disable():
    """
    @notice 
        Disable the inclusion vote procedure.
        No new applications are accepted and no-one is allowed to vote
    """
    assert msg.sender == self.management
    self.enabled = False
    log Enable(False)

@external
def set_application_fee_token(_token: address):
    """
    @notice Set token in which application fees are charged
    @param _token Token in which fees are charged
    """
    assert msg.sender == self.management
    assert _token != empty(address)
    self.fee_token = _token
    log SetFeeToken(_token)

@external
def set_application_fees(_initial: uint256, _subsequent: uint256):
    """
    @notice Set application fees
    @param _initial Initial fee, to be paid on first application
    @param _subsequent Subsequent fee, to be paid on any follow up application
    """
    assert msg.sender == self.management
    self.initial_fee = _initial
    self.subsequent_fee = _subsequent
    log SetFees(_initial, _subsequent)

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
