# @version 0.3.7

interface StaFiToken:
    def getEthValue(_amount: uint256) -> uint256: view

interface StaFiBalances:
    def getTotalRETHSupply() -> uint256: view
    def getTotalETHBalance() -> uint256: view

ASSET: constant(address) = 0x9559Aaa82d9649C7A7b220E7c461d2E74c9a3593 # rETH
BALANCES: constant(address) = 0xda9726Fd1B125a3923f9D9521e28fE888091698d
UNIT: constant(uint256) = 1_000_000_000_000_000_000

@external
@view
def rate(_asset: address) -> uint256:
    assert _asset == ASSET
    return StaFiBalances(BALANCES).getTotalETHBalance() * UNIT / StaFiBalances(BALANCES).getTotalRETHSupply()
