# @version 0.3.7

from vyper.interfaces import ERC4626

ASSET: constant(address) = 0x9Ba021B0a9b958B5E75cE9f6dff97C7eE52cb3E6 # apxETH
UNIT: constant(uint256) = 1_000_000_000_000_000_000

@external
@view
def rate(_asset: address) -> uint256:
    assert _asset == ASSET
    return ERC4626(ASSET).convertToAssets(UNIT)
