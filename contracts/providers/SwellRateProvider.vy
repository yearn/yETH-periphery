# @version 0.3.7

interface SwellToken:
    def swETHToETHRate() -> uint256: view

ASSET: constant(address) = 0xf951E335afb289353dc249e82926178EaC7DEd78 # swETH

@external
@view
def rate(_asset: address) -> uint256:
    assert _asset == ASSET
    return SwellToken(ASSET).swETHToETHRate()
