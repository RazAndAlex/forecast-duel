"""The 10 forecasted assets and the 3 competing models."""

ASSETS = [
    ("ENI.MI", "Eni", "stock"),
    ("ISP.MI", "Intesa Sanpaolo", "stock"),
    ("UCG.MI", "UniCredit", "stock"),
    ("ENEL.MI", "Enel", "stock"),
    ("STLAM.MI", "Stellantis", "stock"),
    ("RACE.MI", "Ferrari", "stock"),
    ("G.MI", "Generali", "stock"),
    ("LDO.MI", "Leonardo", "stock"),
    ("TIT.MI", "Telecom Italia", "stock"),
    ("BTC-USD", "Bitcoin", "crypto"),
]

MODELS = ["kronos", "timestral", "naive"]
