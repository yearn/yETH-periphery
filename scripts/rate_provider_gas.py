from ape import accounts, project

def main():
    deployer = accounts.test_accounts[0]

    providers = [
        # project.BinanceRateProvider,
        project.CoinbaseRateProvider,
        project.FraxRateProvider,
        project.LidoRateProvider,
        project.StaderRateProvider,
        # project.StaFiRateProvider,
        project.SwellRateProvider,
        # project.TranchessRateProvider,
        project.MetaPoolRateProvider,
        project.RocketPoolRateProvider,
        project.MevProtocolRateProvider,
        project.PirexRateProvider,
    ]

    assets = [
        # '0xa2E3356610840701BDf5611a53974510Ae27E2e1', # wBETH
        '0xBe9895146f7AF43049ca1c1AE358B0541Ea49704', # cbETH
        '0xac3E018457B222d93114458476f3E3416Abbe38F', # sfrxETH
        '0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0', # wstETH
        '0xA35b1B31Ce002FBF2058D22F30f95D405200A15b', # ETHx
        # '0x9559Aaa82d9649C7A7b220E7c461d2E74c9a3593', # rETH (StaFi)
        '0xf951E335afb289353dc249e82926178EaC7DEd78', # swETH
        # '0x93ef1Ea305D11A9b2a3EbB9bB4FCc34695292E7d'  # qETH
        '0x48AFbBd342F64EF8a9Ab1C143719b63C2AD81710', # mpETH
        '0xae78736Cd615f374D3085123A210448E74Fc6393', # rETH
        '0x24Ae2dA0f361AA4BE46b48EB19C91e02c5e4f27E', # mevETH
        '0x9Ba021B0a9b958B5E75cE9f6dff97C7eE52cb3E6' # apxETH
    ]

    measure = project.RateProviderMeasure.deploy(sender=deployer)
    measurements = []
    for provider, asset in zip(providers, assets):
        p = provider.deploy(sender=deployer)
        baseline = measure.baseline(p, asset, sender=deployer).gas_used
        measurements.append(repr(provider)[1:-13].ljust(11)+': '+str(measure.rate(p, asset, sender=deployer).gas_used - baseline))

    for measurement in measurements:
        print(measurement)
