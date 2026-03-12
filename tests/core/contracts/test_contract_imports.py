def test_core_contract_package_is_importable():
    from miniautogen.core.contracts import __all__

    assert isinstance(__all__, list)
