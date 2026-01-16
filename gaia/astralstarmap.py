def BPRP_to_teff(bprp):
    """returns in kelvins"""
    teff = 5040/(0.4929+0.5092*bprp-0.0353*bprp**2)
    print("teff:",teff)
    return teff
