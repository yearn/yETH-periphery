# @version 0.3.10
"""
@title Incentives for inclusion vote
@author 0xkorin, Yearn Finance
@license GNU AGPLv3
@notice
    Permissionlessly submit incentives for assets inclusion in the pool.
    Incentives are only paid out for the winning asset each epoch,
    all other incentives are refunded.
    Winner's incentives are paid out to all voters, regardless of whether they voted
    on the winner or on another candidate.
    Incentives that remain unclaimed for a preconfigured number of epochs
    are considered expired and can be swept away.
"""

from vyper.interfaces import ERC20

interface Voting:
    def genesis() -> uint256: view
    def latest_finalized_epoch() -> uint256: view
    def winners(_epoch: uint256) -> address: view
    def total_votes(_epoch: uint256) -> uint256: view
    def votes_user(_account: address, _epoch: uint256) -> uint256: view

genesis: public(immutable(uint256))
voting: public(immutable(Voting))
management: public(address)
pending_management: public(address)
treasury: public(address)
fee_rate: public(uint256)
incentives: public(HashMap[uint256, HashMap[address, HashMap[address, uint256]]]) # epoch => candidate => incentive token => incentive amount
incentives_depositor: public(HashMap[address, HashMap[uint256, HashMap[address, HashMap[address, uint256]]]]) # depositor => epoch => candidate => incentive token => incentive amount
unclaimed: public(HashMap[uint256, HashMap[address, uint256]]) # epoch => incentive token => incentive amount
user_claimed: public(HashMap[address, HashMap[uint256, HashMap[address, bool]]]) # account => epoch => incentive token => claimed?
deposit_deadline: public(uint256)
claim_deadline: public(uint256)

event Deposit:
    epoch: indexed(uint256)
    candidate: indexed(address)
    token: indexed(address)
    amount: uint256
    depositor: address

event Claim:
    epoch: indexed(uint256)
    token: indexed(address)
    amount: uint256
    account: indexed(address)

event Refund:
    epoch: indexed(uint256)
    candidate: indexed(address)
    token: indexed(address)
    amount: uint256
    depositor: address

event Sweep:
    epoch: indexed(uint256)
    token: indexed(address)
    amount: uint256
    recipient: address

event SetTreasury:
    treasury: indexed(address)

event SetDepositDeadline:
    deadline: uint256

event SetClaimDeadline:
    deadline: uint256

event PendingManagement:
    management: indexed(address)

event SetManagement:
    management: indexed(address)

WEEK: constant(uint256) = 7 * 24 * 60 * 60
EPOCH_LENGTH: constant(uint256) = 4 * WEEK
FEE_SCALE: constant(uint256) = 10_000

@external
def __init__(_voting: address):
    """
    @notice Constructor
    @param _voting The inclusion voting contract
    """
    voting = Voting(_voting)
    genesis = voting.genesis()
    self.management = msg.sender
    self.treasury = msg.sender
    self.deposit_deadline = EPOCH_LENGTH
    self.claim_deadline = 1

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
def deposit(_candidate: address, _token: address, _amount: uint256):
    """
    @notice 
        Deposit an incentive. Only allowed in the beginning of an epoch.
        Management can set a deadline after which no new incentives can be deposited.
    @param _candidate
        The candidate token address to place the incentive on.
        The zero address represents the 'blank' option, meaning no new
        asset is to be added to the pool.
    @param _token The incentive token to deposit
    @param _amount The amount of incentive token to deposit
    """
    assert (block.timestamp - genesis) % EPOCH_LENGTH <= self.deposit_deadline
    epoch: uint256 = self._epoch()
    fee: uint256 = _amount * self.fee_rate / FEE_SCALE
    self.incentives[epoch][_candidate][_token] += _amount - fee
    self.incentives_depositor[msg.sender][epoch][_candidate][_token] += _amount
    self.unclaimed[epoch][_token] += _amount

    assert ERC20(_token).transferFrom(msg.sender, self, _amount, default_return_value=True)
    log Deposit(epoch, _candidate, _token, _amount, msg.sender)

@external
@view
def claimable(_epoch: uint256, _token: address, _account: address) -> uint256:
    """
    @notice Query the amount of incentive that can be claimed by a specific account
    @param _epoch Epoch to query for
    @param _token Incentive token to query for
    @param _account Claimer to query for
    """
    winner: address = voting.winners(_epoch)
    if voting.latest_finalized_epoch() < _epoch or self.user_claimed[_account][_epoch][_token]:
        return 0
    
    total_votes: uint256 = voting.total_votes(_epoch)
    if total_votes == 0:
        return 0
    votes: uint256 = voting.votes_user(_account, _epoch)
    return self.incentives[_epoch][winner][_token] * votes / total_votes

@external
def claim_many(_epochs: DynArray[uint256, 16], _tokens: DynArray[address, 16], _account: address = msg.sender):
    """
    @notice Claim one or multiple incentives at once
    @param _epochs List of epochs to claim for
    @param _tokens List of tokens to claim for, corresponding to the list of epochs
    @param _account Account to claim for
    """
    assert len(_epochs) == len(_tokens)
    for i in range(16):
        if i == len(_epochs):
            break
        self._claim(_epochs[i], _tokens[i], _account)

@external
def claim(_epoch: uint256, _token: address, _account: address = msg.sender):
    """
    @notice
        Claim an incentive. Incentives are claimable if the candidate received 
        the most amount of votes in the epoch in question, and are split amongst
        all voters, regardless whether they voted for the winner or not.
    @param _epoch Epoch to claim for
    @param _token Tokens to claim for
    @param _account Account to claim for
    """
    self._claim(_epoch, _token, _account)

@internal
def _claim(_epoch: uint256, _token: address, _account: address):
    """
    @notice Claim an incentive
    """
    assert voting.latest_finalized_epoch() >= _epoch
    winner: address = voting.winners(_epoch)
    total_votes: uint256 = voting.total_votes(_epoch)
    if total_votes == 0:
        return
    votes: uint256 = voting.votes_user(_account, _epoch)
    amount: uint256 = self.incentives[_epoch][winner][_token] * votes / total_votes
    if self.user_claimed[_account][_epoch][_token] or amount == 0:
        return
    self.user_claimed[_account][_epoch][_token] = True
    self.unclaimed[_epoch][_token] -= amount

    assert ERC20(_token).transfer(_account, amount, default_return_value=True)
    log Claim(_epoch, _token, amount, _account)

@external
@view
def refundable(_epoch: uint256, _candidate: address, _token: address, _depositor: address = msg.sender) -> uint256:
    """
    @notice Query whether an incentive can be refunded
    @param _epoch Epoch to query for
    @param _candidate Candidate token to query for
    @param _token Incentive token to query for
    @param _depositor Incentive depositor to query for
    """
    winner: address = voting.winners(_epoch)
    if voting.latest_finalized_epoch() < _epoch or (winner == _candidate and voting.total_votes(_epoch) > 0):
        return 0
    return self.incentives_depositor[_depositor][_epoch][_candidate][_token]

@external
def refund(_epoch: uint256, _candidate: address, _token: address, _depositor: address = msg.sender):
    """
    @notice
        Refund an incentive. Incentives can be refunded if the candidate token has not
        received the most amount of votes and therefore has lost.
    @param _epoch Epoch to refund for
    @param _candidate Candidate token to refund for
    @param _token Incentive token to refund
    @param _depositor Incentive depositor to refund for
    """
    assert voting.latest_finalized_epoch() >= _epoch
    assert voting.winners(_epoch) != _candidate or voting.total_votes(_epoch) == 0

    amount: uint256 = self.incentives_depositor[_depositor][_epoch][_candidate][_token]
    assert amount > 0
    self.incentives_depositor[_depositor][_epoch][_candidate][_token] = 0
    self.unclaimed[_epoch][_token] -= amount

    assert ERC20(_token).transfer(_depositor, amount, default_return_value=True)
    log Refund(_epoch, _candidate, _token, amount, _depositor)

@external
@view
def sweepable(_epoch: uint256, _token: address) -> uint256:
    """
    @notice Query whether an incentive can be swept
    @param _epoch Epoch to query for
    @param _token Incentive token to query for
    """
    if self._epoch() <= _epoch + self.claim_deadline:
        return 0
    return self.unclaimed[_epoch][_token]

@external
def sweep(_epoch: uint256, _token: address, _recipient: address = msg.sender):
    """
    @notice
        Sweep unclaimed incentives. Incenties that remain unclaimed for a set
        number of epochs expire and can be swept by treasury.
    @param _epoch Epoch to sweep for
    @param _token Incentive token to sweep
    @param _recipient Recipient of the swept incentives
    """
    assert msg.sender == self.treasury
    assert self._epoch() > _epoch + self.claim_deadline

    amount: uint256 = self.unclaimed[_epoch][_token]
    assert amount > 0
    self.unclaimed[_epoch][_token] = 0

    assert ERC20(_token).transfer(_recipient, amount, default_return_value=True)
    log Sweep(_epoch, _token, amount, _recipient)

@external
def set_treasury(_treasury: address):
    """
    @notice Set the new treasury address. Treasury can sweep expired unclaimed incentives
    @param _treasury New treasury address
    """
    assert msg.sender == self.treasury
    assert _treasury != empty(address)
    self.treasury = _treasury
    log SetTreasury(_treasury)

@external
def set_deposit_deadline(_deadline: uint256):
    """
    @notice 
        Set the deposit deadline in seconds, after which in every epoch
        incentives are no longer allowed to be posted.
    @param _deadline New deposit deadline in seconds from the start of the epoch
    """
    assert msg.sender == self.management
    assert _deadline <= EPOCH_LENGTH
    self.deposit_deadline = _deadline
    log SetDepositDeadline(_deadline)

@external
def set_claim_deadline(_deadline: uint256):
    """
    @notice 
        Set the claim deadline in epochs, after which unclaimed incentives 
        are considered expired and can be swept by treasury.
    @param _deadline New claim deadline in epochs
    """
    assert msg.sender == self.management
    assert _deadline >= 1
    self.claim_deadline = _deadline
    log SetClaimDeadline(_deadline)

@external
def set_fee_rate(_fee_rate: uint256):
    """
    @notice Set the incentive fee rate
    @param _fee_rate New fee rate (bps)
    """
    assert msg.sender == self.management
    assert _fee_rate <= FEE_SCALE / 10
    self.fee_rate = _fee_rate

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
