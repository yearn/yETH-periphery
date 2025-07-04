# pragma version 0.3.10
# pragma optimize gas
# pragma evm-version cancun

from vyper.interfaces import ERC4626

interface CoinbaseToken:
    def exchangeRate() -> uint256: view

interface LidoToken:
    def getPooledEthByShares(_shares: uint256) -> uint256: view

struct StaderExchangeRate:
    block_number: uint256
    eth_balance: uint256
    ethx_supply: uint256

interface StaderOracle:
    def getExchangeRate() -> StaderExchangeRate: view

interface SwellToken:
    def swETHToETHRate() -> uint256: view

interface RocketPoolBalances:
    def getTotalRETHSupply() -> uint256: view
    def getTotalETHBalance() -> uint256: view

interface RocketPoolStorage():
    def getAddress(_key: bytes32) -> RocketPoolBalances: view

COINBASE_ASSET: constant(address) = 0xBe9895146f7AF43049ca1c1AE358B0541Ea49704 # cbETH
FRAX_ASSET: constant(address) = 0xac3E018457B222d93114458476f3E3416Abbe38F # sfrxETH
LIDO_ASSET: constant(address) = 0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0 # wstETH
STADER_ASSET: constant(address) = 0xA35b1B31Ce002FBF2058D22F30f95D405200A15b # ETHx
SWELL_ASSET: constant(address) = 0xf951E335afb289353dc249e82926178EaC7DEd78 # swETH
ROCKET_POOL_ASSET: constant(address) = 0xae78736Cd615f374D3085123A210448E74Fc6393 # rETH
PIREX_ASSET: constant(address) = 0x9Ba021B0a9b958B5E75cE9f6dff97C7eE52cb3E6 # apxETH

LIDO_UDERLYING: constant(address) = 0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84 # stETH
STADER_ORACLE: constant(address) = 0xF64bAe65f6f2a5277571143A24FaaFDFC0C2a737
ROCKET_POOL_STORAGE: constant(address) = 0x1d8f8f00cfa6758d7bE78336684788Fb0ee0Fa46
UNIT: constant(uint256) = 1_000_000_000_000_000_000

@external
@view
def rate(_asset: address) -> uint256:
    if _asset == COINBASE_ASSET:
        return CoinbaseToken(COINBASE_ASSET).exchangeRate()
    if _asset == FRAX_ASSET:
        return ERC4626(FRAX_ASSET).convertToAssets(UNIT)
    if _asset == LIDO_ASSET:
        return LidoToken(LIDO_UDERLYING).getPooledEthByShares(UNIT)
    if _asset == STADER_ASSET:
        res: StaderExchangeRate = StaderOracle(STADER_ORACLE).getExchangeRate()
        return res.eth_balance * UNIT / res.ethx_supply
    if _asset == SWELL_ASSET:
        return SwellToken(SWELL_ASSET).swETHToETHRate()
    if _asset == ROCKET_POOL_ASSET:
        balances: RocketPoolBalances = RocketPoolStorage(ROCKET_POOL_STORAGE).getAddress(
            keccak256('contract.addressrocketNetworkBalances')
        )
        return balances.getTotalETHBalance() * UNIT / balances.getTotalRETHSupply()
    if _asset == PIREX_ASSET:
        return ERC4626(PIREX_ASSET).convertToAssets(UNIT)
    raise
