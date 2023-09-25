# @version 0.3.7
"""
@title Pool executor
@author 0xkorin, Yearn Finance
@license GNU AGPLv3
"""

from vyper.interfaces import ERC20

interface Pool:
    def num_assets() -> uint256: view
    def amplification() -> uint256: view
    def weight(_idx: uint256) -> uint256: view

interface InclusionVote:
    def latest_finalized_epoch() -> uint256: view
    def winners(_epoch: uint256) -> address: view
    def winner_rate_providers(_epoch: uint256) -> address: view

interface WeightVote:
    def total_votes(_epoch: uint256) -> uint256: view
    def votes(_epoch: uint256, _idx: uint256) -> uint256: view

interface Executor:
    def execute_single(_to: address, _data: Bytes[2048]): nonpayable

genesis: public(immutable(uint256))
pool: public(immutable(address))
management: public(address)
pending_management: public(address)
executor: public(address)
operator: public(address)
initial_weight: public(uint256)
ramp_weight: public(uint256)
redistribute_weight: public(uint256)
target_amplification: public(uint256)
ramp_duration: public(uint256)
inclusion_vote: public(address)
weight_vote: public(address)
latest_executed_epoch: public(uint256)

event PendingManagement:
    management: indexed(address)

event SetManagement:
    management: indexed(address)

EPOCH_LENGTH: constant(uint256) = 4 * 7 * 24 * 60 * 60
APPLICATION_DISABLED: constant(address) = 0x0000000000000000000000000000000000000001
PRECISION: constant(uint256) = 10**18

@external
def __init__(_genesis: uint256, _pool: address, _executor: address):
    genesis = _genesis
    pool = _pool
    self.management = msg.sender
    self.executor = _executor
    self.operator = msg.sender

    self.latest_executed_epoch = self._epoch() - 1
    self.initial_weight = PRECISION / 10_000
    self.ramp_weight = PRECISION / 100
    self.redistribute_weight = PRECISION / 10
    self.target_amplification = Pool(pool).amplification()
    self.ramp_duration = 7 * 24 * 60 * 60

@external
@view
def epoch() -> uint256:
    return self._epoch()

@internal
@view
def _epoch() -> uint256:
    return (block.timestamp - genesis) / EPOCH_LENGTH

@external
def execute(_lower: uint256, _upper: uint256, _amount: uint256, _amplification: uint256, _min_lp_amount: uint256):
    epoch: uint256 = self._epoch() - 1
    iv: InclusionVote = InclusionVote(self.inclusion_vote)
    assert msg.sender == self.operator
    assert self.latest_executed_epoch < epoch
    assert iv.latest_finalized_epoch() == epoch
    self.latest_executed_epoch = epoch

    num_assets: uint256 = Pool(pool).num_assets()
    winner: address = iv.winners(epoch)
    provider: address = iv.winner_rate_providers(epoch)
    included: bool = winner != empty(address) and provider not in [empty(address), APPLICATION_DISABLED]

    # calculate weight to redistribute, taking into account blank votes
    v: WeightVote = WeightVote(self.weight_vote)
    total_votes: uint256 = v.total_votes(epoch)
    redistribute: uint256 = 0
    if total_votes > 0:
        blank: uint256 = v.votes(epoch, 0)
        redistribute = self.redistribute_weight * (total_votes - blank) / total_votes
        total_votes -= blank
    if total_votes == 0 and not included:
        # no votes, no new asset
        return
    left: uint256 = redistribute
    if included:
        left += self.ramp_weight
    left = PRECISION - left

    # calculate new weights
    weights: DynArray[uint256, 32] = []
    total_weight: uint256 = 0
    for i in range(32):
        if i == num_assets:
            break
        weight: uint256 = Pool(pool).weight(i) * left / PRECISION
        if total_votes > 0:
            weight += redistribute * v.votes(epoch, i + 1) / total_votes
        weights.append(weight)
        total_weight += weight

    if included:
        weights.append(self.ramp_weight)
        total_weight += self.ramp_weight

        # approve spending of winning token
        # assume that token was transferred to ultimate executor prior to calling this function    
        data: Bytes[2048] = _abi_encode(pool, _amount, method_id=method_id('approve(address,uint256)'))
        Executor(self.executor).execute_single(winner, data)

        # add new asset to pool
        data = _abi_encode(
            winner, provider, self.initial_weight, _lower, _upper, _amount, 
            _amplification, _min_lp_amount, msg.sender,
            method_id=method_id(
                'add_asset(address,address,uint256,uint256,uint256,uint256,uint256,uint256,address)'
            )
        )
        Executor(self.executor).execute_single(pool, data)        
    else:
        num_assets -= 1
    
    # correct for rounding
    if total_weight > PRECISION:
        weights[num_assets] -= total_weight - PRECISION
    else:
        weights[num_assets] += PRECISION - total_weight

    # execute ramp
    data: Bytes[2048] = _abi_encode(
        self.target_amplification, weights, self.ramp_duration, 
        method_id=method_id('set_ramp(uint256,uint256[],uint256)')
    )
    Executor(self.executor).execute_single(pool, data)

@external
def set_target_amplification(_target: uint256):
    assert msg.sender == self.management
    self.target_amplification = _target

@external
def set_executor(_executor: address):
    assert msg.sender == self.management
    assert _executor != empty(address)
    self.executor = _executor

@external
def set_operator(_operator: address):
    assert msg.sender == self.management
    assert _operator != empty(address)
    self.operator = _operator

@external
def set_initial_weight(_weight: uint256):
    assert msg.sender == self.management
    self.initial_weight = _weight

@external
def set_ramp_weight(_weight: uint256):
    assert msg.sender == self.management
    self.ramp_weight = _weight

@external
def set_redistribute_weight(_weight: uint256):
    assert msg.sender == self.management
    self.redistribute_weight = _weight

@external
def set_ramp_duration(_duration: uint256):
    assert msg.sender == self.management
    self.ramp_duration = _duration

@external
def set_inclusion_vote(_inclusion: address):
    assert msg.sender == self.management
    assert _inclusion != empty(address)
    self.inclusion_vote = _inclusion

@external
def set_weight_vote(_weight: address):
    assert msg.sender == self.management
    assert _weight != empty(address)
    self.weight_vote = _weight

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
