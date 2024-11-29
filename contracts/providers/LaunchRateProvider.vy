# @version 0.3.10

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

COINBASE_ASSET: constant(address) = 0xBe9895146f7AF43049ca1c1AE358B0541Ea49704 # cbETH
FRAX_ASSET: constant(address) = 0xac3E018457B222d93114458476f3E3416Abbe38F # sfrxETH
LIDO_ASSET: constant(address) = 0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0 # wstETH
STADER_ASSET: constant(address) = 0xA35b1B31Ce002FBF2058D22F30f95D405200A15b # ETHx
SWELL_ASSET: constant(address) = 0xf951E335afb289353dc249e82926178EaC7DEd78 # swETH

LIDO_UDERLYING: constant(address) = 0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84 # stETH
STADER_ORACLE: constant(address) = 0xF64bAe65f6f2a5277571143A24FaaFDFC0C2a737
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
    raise
