EXCHANGES_BY_COUNTRY = {
    "AR": ["BUE"],  # Argentina (Buenos Aires)
    "AT": ["VIE"],  # Austria (Vienna)
    "AU": ["ASX"],  # Australia
    "BE": ["BRU"],  # Belgium (Brussels)
    "BR": ["SAO"],  # Brazil (São Paulo)
    "CA": ["CNQ", "NEO", "TOR", "VAN"],  # Canada
    "CH": ["EBS"],  # Switzerland (Electronic Board Swiss)
    "CL": ["SGO"],  # Chile (Santiago)
    "CN": ["SHH", "SHZ"],  # China (Shanghai, Shenzhen)
    "CO": ["BVC"],  # Colombia
    "CZ": ["PRA"],  # Czech Republic (Prague)
    "DE": ["BER", "DUS", "FRA", "GER", "HAM", "MUN", "STU"],  # Germany
    "DK": ["CPH"],  # Denmark (Copenhagen)
    "EE": ["TAL"],  # Estonia (Tallinn)
    "EG": ["CAI"],  # Egypt (Cairo)
    "ES": ["MCE"],  # Spain (Madrid Continuous Market)
    "FI": ["HEL"],  # Finland (Helsinki)
    "FR": ["PAR"],  # France (Paris)
    "GB": ["AQS", "IOB", "LSE"],  # United Kingdom
    "GR": ["ATH"],  # Greece (Athens)
    "HK": ["HKG"],  # Hong Kong
    "HU": ["BUD"],  # Hungary (Budapest)
    "ID": ["JKT"],  # Indonesia (Jakarta)
    "IE": ["ISE"],  # Ireland (Eurnext Dublin)
    "IL": ["TLV"],  # Israel (Tel Aviv)
    "IN": ["BSE", "NSI"],  # India (Bombay, National Stock Exchange)
    "IS": ["ICE"],  # Iceland
    "IT": ["MIL"],  # Italy (Milan)
    "JP": ["FKA", "JPX", "SAP"],  # Japan (Fukuoka, Tokyo, Sapporo)
    "KR": ["KOE", "KSC"],  # South Korea (KOSDAQ, KSE)
    "KW": ["KUW"],  # Kuwait
    "LT": ["LIT"],  # Lithuania (Vilnius)
    "LV": ["RIS"],  # Latvia (Riga)
    "MX": ["MEX"],  # Mexico
    "MY": ["KLS"],  # Malaysia (Kuala Lumpur)
    "NL": ["AMS"],  # Netherlands (Amsterdam)
    "NO": ["OSL"],  # Norway (Oslo)
    "NZ": ["NZE"],  # New Zealand
    "PH": ["PHP", "PHS"],  # Philippines
    "PL": ["WSE"],  # Poland (Warsaw)
    "PT": ["LIS"],  # Portugal (Lisbon)
    "QA": ["DOH"],  # Qatar (Doha)
    "RO": ["BVB"],  # Romania (Bucharest)
    "SA": ["SAU"],  # Saudi Arabia
    "SE": ["STO"],  # Sweden (Stockholm)
    "SG": ["SES"],  # Singapore
    "TH": ["SET"],  # Thailand
    "TR": ["IST"],  # Turkey (Istanbul)
    "TW": ["TAI", "TWO"],  # Taiwan (TWSE, OTC)
    "US": ["ASE", "BTS", "CXI", "NCM", "NGM", "NMS", "NYQ", "OEM", "OQB", "OQX", "PCX", "PNK", "YHD"],  # USA (NYSE, NASDAQ, OTC, etc.)
    "VE": ["CCS"],  # Venezuela (Caracas)
}


EXCHANGES = [
    "AMS", "AQS", "ASE", "ASX", "ATH", "BER", "BRU", "BSE", "BTS", "BUD",
    "BUE", "BVB", "BVC", "CAI", "CCS", "CNQ", "CPH", "CXI", "DOH", "DUS",
    "EBS", "FKA", "FRA", "GER", "HAM", "HEL", "HKG", "ICE", "IOB", "ISE",
    "IST", "JKT", "JNB", "JPX", "KLS", "KOE", "KSC", "KUW", "LIS", "LIT",
    "LSE", "MCE", "MEX", "MIL", "MUN", "NCM", "NEO", "NGM", "NMS", "NSI",
    "NYQ", "NZE", "OEM", "OQB", "OQX", "OSL", "PAR", "PCX", "PHP", "PHS",
    "PNK", "PRA", "RIS", "SAO", "SAP", "SAU", "SES", "SET", "SGO", "SHH",
    "SHZ", "STO", "STU", "TAI", "TAL", "TLV", "TOR", "TWO", "VAN", "VIE",
    "WSE", "YHD",
]

def get_exchanes_by_countries(country_codes: list[str]) -> list[str]:
    exchanges = []
    for code in country_codes:
        exchanges.extend(EXCHANGES_BY_COUNTRY.get(code, []))
    return exchanges
