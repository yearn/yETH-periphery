# pragma version 0.3.10
# pragma optimize gas
# pragma evm-version cancun

from vyper.interfaces import ERC20

interface Pool:
    def exchange(i: int128, j: int128, _dx: uint256, _min_dy: uint256) -> uint256: nonpayable

weth: public(immutable(ERC20))
yeth: public(immutable(ERC20))
management: public(address)
pending_management: public(address)
operator: public(address)

@external
def __init__(_weth: address, _yeth: address):
    weth = ERC20(_weth)
    yeth = ERC20(_yeth)
    self.management = msg.sender
    self.operator = msg.sender

@external
def convert(_pool: address, _i: int128, _j: int128, _amount: uint256, _min_amount_out: uint256):
    assert msg.sender == self.operator
    assert _pool != empty(address)
    assert _amount > 0
    assert _min_amount_out >= _amount
    assert weth.transferFrom(self.management, self, _amount, default_return_value=True)
    assert weth.approve(_pool, _amount, default_return_value=True)
    Pool(_pool).exchange(_i, _j, _amount, _min_amount_out)
    amount_out: uint256 = yeth.balanceOf(self)
    assert amount_out >= _min_amount_out
    assert yeth.transfer(self.management, amount_out, default_return_value=True)

@external
def rescue(_token: address, _amount: uint256 = max_value(uint256)):
    assert msg.sender == self.management
    amount: uint256 = _amount
    if _amount == max_value(uint256):
        amount = ERC20(_token).balanceOf(self)
    assert ERC20(_token).transfer(msg.sender, amount, default_return_value=True)

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
