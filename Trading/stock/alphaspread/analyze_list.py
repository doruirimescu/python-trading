from Trading.stock.alphaspread.alphaspread import analyze_url
from Trading.stock.alphaspread.url import get_alphaspread_symbol_url, get_alphaspread_url_from_ticker



NAMES = [     "BioSymetrics",
    "Iktos",
    "Genesis Therapeutics",
    "Spring Discovery",
    "1859",
    "Vilya",
    "Persephone Biosciences",
    "Biotia",
    "PostEra",
    "Totus Medicines"]
for name in NAMES:
    try:
        symbol, url = get_alphaspread_url_from_ticker(name)
    except Exception:
        try:
            symbol, url = get_alphaspread_symbol_url(name)
        except Exception:
            continue
    try:
        # Analyze the symbol
        analysis = analyze_url(url, symbol)

        # Print the analysis
        print(analysis)

    except Exception as e:
        pass

# AI drug discovery and pharmaceuticals
# Symbol exai is Undervalued by 26% with solvency: 59% and profitability: 17%
# Symbol mdt is Undervalued by 11% with solvency: 54% and profitability: 57%.
# Symbol tgtx is Undervalued by 22% with solvency: 61% and profitability: 42%.
# Symbol ICL is Undervalued by 5% with solvency: 67% and profitability: 58%.
# Symbol dim is Overvalued by 28% with solvency: 42% and profitability: 60%
