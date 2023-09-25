# @version 0.3.7
"""
@title Pool governor
@author 0xkorin, Yearn Finance
@license GNU AGPLv3
@notice
    Governs the addition of new assets and ramping of weights throught the governance executor.
    Relies on results from the inclusion and weight voting contracts.
    If the inclusion vote resulted in a winner, this contract will add it to the pool
    with a small weight. Next, it will schedule a ramp based on the results from the weight voting
    contracts. A percentage of each assets weight is subtracted and redistributed according to
    amount of votes for each asset. Simultaneously the weight of the newly added asset is ramped up.

    The operator is a trusted role with very limited powers. They are tasked with setting parameters
    such that the new asset is added with minimal arb opportunities. Outside of these safety conditions 
    it has no power to change the new to be added asset or any of the weights.
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

event AddAsset:
    epoch: indexed(uint256)
    asset: indexed(address)
    lower_band: uint256
    upper_band: uint256
    amount: uint256
    amplification: uint256

event StartRamp:
    epoch: indexed(uint256)

event SetValue:
    field: indexed(uint256)
    value: uint256

event SetExecutor:
    executor: indexed(address)

event SetOperator:
    operator: indexed(address)

event PendingManagement:
    management: indexed(address)

event SetManagement:
    management: indexed(address)

EPOCH_LENGTH: constant(uint256) = 4 * 7 * 24 * 60 * 60
APPLICATION_DISABLED: constant(address) = 0x0000000000000000000000000000000000000001
PRECISION: constant(uint256) = 10**18

@external
def __init__(_genesis: uint256, _pool: address, _executor: address):
    """
    @notice Constructor
    @param _genesis Timestamp of start of epoch 0
    @param _pool Pool address
    @param _executor Governance executor address
    """
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
def execute(_lower: uint256, _upper: uint256, _amount: uint256, _amplification: uint256, _min_lp_amount: uint256):
    """
    @notice 
        Add new asset and ramp weights through the governance executor.
        Operator should pick values in such a way to minimize arb opportunities 
        introduced by adding a new asset to the pool.
    @param _lower Lower weight band (18 decimals)
    @param _upper Upper weight band (18 decimals)
    @param _amount Amount of token to transfer to the pool, in exchange for LP token
    @param _amplification The amplification to set simultaneously with adding the new asset
    @param _min_lp_amount Minimum amount of LP tokens to receive
    """
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
        log AddAsset(epoch, winner, _lower, _upper, _amount, _amplification)
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
    log StartRamp(epoch)
    Executor(self.executor).execute_single(pool, data)

@external
def set_target_amplification(_target: uint256):
    """
    @notice Set the target amplification factor for the next ramp
    @param _target Target amplification factor
    """
    assert msg.sender == self.management
    self.target_amplification = _target
    log SetValue(0, _target)

@external
def set_executor(_executor: address):
    """
    @notice Set the governance executor
    @param _executor Governance executor
    """
    assert msg.sender == self.management
    assert _executor != empty(address)
    self.executor = _executor
    log SetExecutor(_executor)

@external
def set_operator(_operator: address):
    """
    @notice Set the operator
    @param _operator Operator
    """
    assert msg.sender == self.management or msg.sender == self.operator
    assert _operator != empty(address)
    self.operator = _operator
    log SetOperator(_operator)

@external
def set_initial_weight(_weight: uint256):
    """
    @notice Set the initial weight during addition of new asset to the pool
    @param _weight Initial weight (18 decimals)
    """
    assert msg.sender == self.management
    self.initial_weight = _weight
    log SetValue(1, _weight)

@external
def set_ramp_weight(_weight: uint256):
    """
    @notice Set the ramp target weight of the newly added asset
    @param _weight Ramp target weight (18 decimals)
    """
    assert msg.sender == self.management
    self.ramp_weight = _weight
    log SetValue(2, _weight)

@external
def set_redistribute_weight(_weight: uint256):
    """
    @notice Set the weight that is redistributed according to the votes
    @param _weight Redistribute weight (18 decimals)
    """
    assert msg.sender == self.management
    self.redistribute_weight = _weight
    log SetValue(3, _weight)

@external
def set_ramp_duration(_duration: uint256):
    """
    @notice Set the ramp duration
    @param _duration Ramp duration (seconds)
    """
    assert msg.sender == self.management
    self.ramp_duration = _duration
    log SetValue(4, _duration)

@external
def set_inclusion_vote(_inclusion: address):
    """
    @notice 
        Set the inclusion vote contract that determines which asset should be 
        newly included in the pool.
    @param _inclusion New inclusion vote contract
    """
    assert msg.sender == self.management
    assert _inclusion != empty(address)
    self.inclusion_vote = _inclusion
    log SetValue(5, convert(_inclusion, uint256))

@external
def set_weight_vote(_weight: address):
    """
    @notice 
        Set the weight vote contract that determines the redistribution of
        weights over the assets.
    @param _weight New weight vote contract
    """
    assert msg.sender == self.management
    assert _weight != empty(address)
    self.weight_vote = _weight
    log SetValue(6, convert(_weight, uint256))

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
