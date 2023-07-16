from ape import accounts, project

def main():
    deployer = accounts.test_accounts[0]

    providers = [
        project.FraxRateProvider,
        project.LidoRateProvider,
        project.StaderRateProvider,
        project.StaFiRateProvider,
        project.SwellRateProvider,
        project.TranchessRateProvider
    ]

    assets = [
        '0xac3E018457B222d93114458476f3E3416Abbe38F', # sfrxETH
        '0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0', # wstETH
        '0xA35b1B31Ce002FBF2058D22F30f95D405200A15b', # ETHx
        '0x9559Aaa82d9649C7A7b220E7c461d2E74c9a3593', # rETH
        '0xf951E335afb289353dc249e82926178EaC7DEd78', # swETH
        '0x93ef1Ea305D11A9b2a3EbB9bB4FCc34695292E7d'  # qETH
    ]

    measure = project.RateProviderMeasure.deploy(sender=deployer)
    measurements = []
    for provider, asset in zip(providers, assets):
        p = provider.deploy(sender=deployer)
        baseline = measure.baseline(p, asset, sender=deployer).gas_used
        measurements.append(repr(provider)[1:-13].ljust(9)+': '+str(measure.rate(p, asset, sender=deployer).gas_used - baseline))

    for measurement in measurements:
        print(measurement)
