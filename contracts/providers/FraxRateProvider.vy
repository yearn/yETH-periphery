# @version 0.3.7

from vyper.interfaces import ERC4626

ASSET: constant(address) = 0xac3E018457B222d93114458476f3E3416Abbe38F # sfrxETH
UNIT: constant(uint256) = 1_000_000_000_000_000_000

@external
@view
def rate(_asset: address) -> uint256:
    assert _asset == ASSET
    return ERC4626(ASSET).convertToAssets(UNIT)
