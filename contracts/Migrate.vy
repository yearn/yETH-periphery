# pragma version 0.3.10
# pragma optimize gas
# pragma evm-version cancun

from vyper.interfaces import ERC20

interface Token:
    def mint(_account: address, _amount: uint256): nonpayable
    def burn(_account: address, _amount: uint256): nonpayable

interface Pool:
    def killed() -> bool: view
    def paused() -> bool: view
    def unpause(): nonpayable
    def set_management(_management: address): nonpayable
    def accept_management(): nonpayable
    
    def supply() -> uint256: view
    def assets(_i: uint256) -> address: view
    def update_rates(_assets: DynArray[uint256, 32]): nonpayable
    def add_liquidity(_amounts: DynArray[uint256, 32], _min_lp: uint256) -> uint256: nonpayable
    def remove_liquidity(_lp: uint256, _min: DynArray[uint256, 32]): nonpayable

interface MevEth:
    def withdrawQueue(_amount: uint256, _receiver: address, _owner: address) -> uint256: nonpayable

token: public(immutable(address))
old: public(immutable(Pool))
new: public(immutable(Pool))
meveth: public(immutable(MevEth))

management: public(address)
pending_management: public(address)
operator: public(address)
debt: public(uint256)

@external
def __init__(_token: address, _old: address, _new: address, _meveth: address):
    token = _token
    old = Pool(_old)
    new = Pool(_new)
    meveth = MevEth(_meveth)
    self.management = msg.sender
    self.operator = msg.sender

@external
def migrate():
    assert msg.sender == self.operator
    assert old.killed() and new.paused()

    supply: uint256 = old.supply()
    assert supply > 0

    # unpause new pool
    new.accept_management()
    new.unpause()

    # mint yETH
    Token(token).mint(self, supply)
    self.debt += supply

    # withdraw LSTs from old pool
    old.remove_liquidity(supply, [0, 0, 0, 0, 0, 0, 0, 0])

    # deposit LSTs in new pool
    amounts: DynArray[uint256, 32] = []
    for i in range(7):
        asset: ERC20 = ERC20(new.assets(i))
        assert asset.approve(new.address, max_value(uint256), default_return_value=True)
        amounts.append(asset.balanceOf(self))
    new.add_liquidity(amounts, 0)

@external
def repay(_amount: uint256):
    assert msg.sender == self.operator

    # burn yETH
    self.debt -= _amount
    Token(token).burn(self, _amount)

@external
def withdraw(_amount: uint256):
    assert msg.sender == self.operator

    # queue mevETH withdrawal
    meveth.withdrawQueue(_amount, self.management, self)

@external
def rescue(_token: address, _amount: uint256):
    assert msg.sender == self.management

    if _token == token:
        # can only withdraw excessive yETH
        assert self.debt == 0

    assert ERC20(_token).transfer(msg.sender, _amount, default_return_value=True)

@external
def transfer_pool_management(_management: address):
    assert msg.sender == self.management
    new.set_management(_management)

@external
def set_operator(_operator: address):
    assert msg.sender == self.management
    self.operator = _operator

@external
def set_management(_management: address):
    assert msg.sender == self.management
    self.pending_management = _management

@external
def accept_management():
    assert msg.sender == self.pending_management
    self.pending_management = empty(address)
    self.management = msg.sender
