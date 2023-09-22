def test_launch_provider(project, deployer):
    providers = [
        project.CoinbaseRateProvider,
        project.FraxRateProvider,
        project.LidoRateProvider,
        project.StaderRateProvider,
        project.SwellRateProvider,
    ]

    assets = [
        '0xBe9895146f7AF43049ca1c1AE358B0541Ea49704', # cbETH
        '0xac3E018457B222d93114458476f3E3416Abbe38F', # sfrxETH
        '0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0', # wstETH
        '0xA35b1B31Ce002FBF2058D22F30f95D405200A15b', # ETHx
        '0xf951E335afb289353dc249e82926178EaC7DEd78', # swETH
    ]

    rp = project.LaunchRateProvider.deploy(sender=deployer)
    for provider, asset in zip(providers, assets):
        p = provider.deploy(sender=deployer)
        assert rp.rate(asset) == p.rate(asset)
