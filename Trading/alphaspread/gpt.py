import yfinance as yf
import pandas as pd
import itertools

def calculate_cagr(end_value, start_value, periods):
    return (end_value/start_value)**(1/periods)-1

def portfolio_cagr(cagr1, cagr2, weight1, weight2):
    return cagr1 * weight1 + cagr2 * weight2


# List of European stock tickers (you would need a comprehensive list here)
european_stocks = [
    "ULVR.L",   # Unilever
    "AZN.L",    # AstraZeneca
    "BP.L",     # BP
    "VOD.L",    # Vodafone Group
    "DGE.L",    # Diageo
    "SIE.DE",   # Siemens
    "SAP.DE",   # SAP
    "VOW3.DE",  # Volkswagen
    "BAS.DE",   # BASF
    "BAYN.DE",  # Bayer
    "OR.PA",    # L'Oréal
    "TOTF.PA",  # Total
    "SAN.PA",   # Sanofi
    "AIR.PA",   # Airbus
    "BNP.PA",   # BNP Paribas
    "NESN.SW",  # Nestlé
    "ROG.SW",   # Roche
    "NOVN.SW",  # Novartis
    "UBSG.SW",  # UBS Group
    "ZURN.SW",  # Zurich Insurance Group
    "ASML.AS",  # ASML
    "RDSa.AS",  # Royal Dutch Shell
    "INGA.AS",  # ING Group
    "PHIA.AS",  # Philips
    "HEIA.AS",  # Heineken
    "SAN.MC",   # Banco Santander
    "TEF.MC",   # Telefónica
    "ITX.MC",   # Inditex
    "IBE.MC",   # Iberdrola
    "REP.MC",   # Repsol
    "ENI.MI",   # ENI
    "CRDI.MI",  # UniCredit
    "LUX.MI",   # Luxottica (Note: Luxottica merged with Essilor)
    "RACE.MI",  # Ferrari
    "FCHA.MI",  # Fiat Chrysler
    "VOLV-B.ST",# Volvo
    "ERIC-B.ST",# Ericsson
    "HM-B.ST",  # H&M
    "NOVO-B.CO",# Novo Nordisk
    "NOKIA.HE"  # Nokia
]


data = []

# Calculate CAGR for each stock
for stock in european_stocks:
    try:
        df = yf.download(stock, start="1990-01-01", end="2021-01-01")
        cagr = calculate_cagr(df['Close'][-1], df['Close'][0], 41)
        data.append((stock, cagr))
    except:
        print(f"Error downloading {stock}")

# Calculate portfolio CAGR for each possible pair of stocks with varying weight allocations
best_cagr = 0
best_pair = ()
best_weights = (0, 0)

for pair in itertools.combinations(data, 2):
    for weight1 in [x * 0.01 for x in range(101)]:
        weight2 = 1 - weight1
        combined_cagr = portfolio_cagr(pair[0][1], pair[1][1], weight1, weight2)
        if combined_cagr > best_cagr:
            best_cagr = combined_cagr
            best_pair = pair
            best_weights = (weight1, weight2)

print(f"The best pair of stocks based on CAGR from 1980-2021 are: {best_pair[0][0]} (weight: {best_weights[0]:.2%}) and {best_pair[1][0]} (weight: {best_weights[1]:.2%}) with a combined CAGR of {best_cagr:.2%}")
