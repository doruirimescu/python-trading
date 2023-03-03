# Fixed conversion rates into eur
#TODO: use client and calculate spot conversion rates.
def convert_currency_to_eur(currency: str):
    currency = currency.upper()
    if currency == "EUR":
        return 1.0
    elif currency == "RON":
        return 0.2
    elif currency == "USD":
        return 0.94
    elif currency == "CHF":
        return 1.0
    elif currency == "HUF":
        return 0.0026
    elif currency == "AUD":
        return 0.64
    elif currency == "NZD":
        return 0.58
    elif currency == "SEK":
        return 0.09
    elif currency == "NOK":
        return 0.091
    else:
        raise ValueError("Currency {currency} not supported")
