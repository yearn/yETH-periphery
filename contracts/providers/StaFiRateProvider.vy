# @version 0.3.7

interface StaFiBalances:
    def getTotalRETHSupply() -> uint256: view
    def getTotalETHBalance() -> uint256: view

interface StaFiStorage():
    def getAddress(_key: bytes32) -> address: view

ASSET: constant(address) = 0x9559Aaa82d9649C7A7b220E7c461d2E74c9a3593 # rETH
STORAGE: constant(address) = 0x6c2f7b6110a37b3B0fbdd811876be368df02E8B0
BALANCES: constant(address) = 0xda9726Fd1B125a3923f9D9521e28fE888091698d
UNIT: constant(uint256) = 1_000_000_000_000_000_000

@external
@view
def rate(_asset: address) -> uint256:
    assert _asset == ASSET
    return StaFiBalances(BALANCES).getTotalETHBalance() * UNIT / StaFiBalances(BALANCES).getTotalRETHSupply()

# for testing purposes
@external
@view
def verify_balances_contract() -> bool:
    balances: address = StaFiStorage(STORAGE).getAddress(keccak256('contract.addressstafiNetworkBalances'))
    return balances == BALANCES
