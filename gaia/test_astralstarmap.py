from astralstarmap import BPRP_to_teff

def test_BPRP_to_Teff():
    bprp =1.0
    teff = BPRP_to_teff(bprp)
    expected_result = 5213.07405875
    actual_result = teff
    assert abs(actual_result -expected_result) <1e-6, f"Expected {expected_result}, but got {actual_result}"


test_BPRP_to_Teff()
