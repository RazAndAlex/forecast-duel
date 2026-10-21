"""The 12 forecasted assets and the 3 competing models."""
from typing import NamedTuple


class Asset(NamedTuple):
    ticker: str
    name: str
    short: str  # for tight labels
    kind: str  # "stock" or "crypto"
    exchange: str  # exchange_calendars code; US listings all use XNYS
    currency: str


ASSETS = [
    Asset("NVDA", "Nvidia", "Nvidia", "stock", "XNYS", "USD"),
    Asset("MSFT", "Microsoft", "Microsoft", "stock", "XNYS", "USD"),
    Asset("GOOGL", "Alphabet", "Alphabet", "stock", "XNYS", "USD"),
    Asset("AMZN", "Amazon", "Amazon", "stock", "XNYS", "USD"),
    Asset("META", "Meta", "Meta", "stock", "XNYS", "USD"),
    Asset("TSM", "TSMC", "TSMC", "stock", "XNYS", "USD"),
    Asset("ASML", "ASML", "ASML", "stock", "XNYS", "USD"),  # the Nasdaq listing
    Asset("PLTR", "Palantir", "Palantir", "stock", "XNYS", "USD"),
    Asset("SIE.DE", "Siemens", "Siemens", "stock", "XETR", "EUR"),
    Asset("STMMI.MI", "STMicroelectronics", "STMicro", "stock", "XMIL", "EUR"),
    Asset("STLAM.MI", "Stellantis", "Stellantis", "stock", "XMIL", "EUR"),
    Asset("RACE.MI", "Ferrari", "Ferrari", "stock", "XMIL", "EUR"),
]

# MILAN_V1: the first asset set. To switch back, replace ASSETS above with this list.
# MILAN_V1 = [
#     Asset("ENI.MI", "Eni", "Eni", "stock", "XMIL", "EUR"),
#     Asset("ISP.MI", "Intesa Sanpaolo", "Intesa", "stock", "XMIL", "EUR"),
#     Asset("UCG.MI", "UniCredit", "UniCredit", "stock", "XMIL", "EUR"),
#     Asset("ENEL.MI", "Enel", "Enel", "stock", "XMIL", "EUR"),
#     Asset("STLAM.MI", "Stellantis", "Stellantis", "stock", "XMIL", "EUR"),
#     Asset("RACE.MI", "Ferrari", "Ferrari", "stock", "XMIL", "EUR"),
#     Asset("G.MI", "Generali", "Generali", "stock", "XMIL", "EUR"),
#     Asset("LDO.MI", "Leonardo", "Leonardo", "stock", "XMIL", "EUR"),
#     Asset("TIT.MI", "Telecom Italia", "TIM", "stock", "XMIL", "EUR"),
#     Asset("BTC-USD", "Bitcoin", "Bitcoin", "crypto", "", "USD"),
# ]

MODELS = ["kronos", "timestral", "naive"]
