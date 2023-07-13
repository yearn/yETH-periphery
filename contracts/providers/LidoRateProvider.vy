# @version 0.3.7

from vyper.interfaces import ERC4626

interface LidoToken:
    def stEthPerToken() -> uint256: view

ASSET: constant(address) = 0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0 # wstETH
UNIT: constant(uint256) = 1_000_000_000_000_000_000

@external
@view
def rate(_asset: address) -> uint256:
    assert _asset == ASSET
    return LidoToken(ASSET).stEthPerToken()
