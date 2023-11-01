# @version 0.3.7

from vyper.interfaces import ERC4626

ASSET: constant(address) = 0x48AFbBd342F64EF8a9Ab1C143719b63C2AD81710 # mpETH
UNIT: constant(uint256) = 1_000_000_000_000_000_000

@external
@view
def rate(_asset: address) -> uint256:
    assert _asset == ASSET
    return ERC4626(ASSET).convertToAssets(UNIT)
