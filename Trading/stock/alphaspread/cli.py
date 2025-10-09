# add cli parser for the symbol
import argparse
from Trading.stock.alphaspread.alphaspread import analyze_url
from Trading.stock.alphaspread.url import get_alphaspread_url


# Create a parser object
parser = argparse.ArgumentParser(description="Get the symbol and url to analyze.")
parser.add_argument("--name", help="The name or symbol of company to analyze.", )

# Parse the arguments
args = parser.parse_args()

# Get the symbol
name = args.name

try:
    symbol, url = get_alphaspread_url(name)
except Exception as e:
    print(e)
    exit(1)

# Analyze the symbol
analysis = analyze_url(url, symbol)

# Print the analysis
print(analysis)

# UGI, ARBOR
