# pragma version 0.3.10
# pragma optimize gas
# pragma evm-version cancun

from vyper.interfaces import ERC20

interface Pool:
    def exchange(i: int128, j: int128, _dx: uint256, _min_dy: uint256) -> uint256: nonpayable
implements: Pool

weth: immutable(ERC20)
amount_out: uint256

@external
def __init__(_weth: address):
    weth = ERC20(_weth)

@external
def set_amount_out(_amount_out: uint256):
    self.amount_out = _amount_out

@external
def exchange(i: int128, j: int128, _dx: uint256, _min_dy: uint256) -> uint256:
    # malicious pool only takes WETH and gives nothing in return
    weth.transferFrom(msg.sender, self, _dx, default_return_value=True)
    return self.amount_out
