# add cli parser for the symbol
import argparse
from Trading.alphaspread.alphaspread import analyze_url
from Trading.alphaspread.url import get_alphaspread_symbol_url


# Create a parser object
parser = argparse.ArgumentParser(description="Get the symbol and url to analyze.")
parser.add_argument("--name", help="The name or symbol of company to analyze.", )

# Parse the arguments
args = parser.parse_args()

# Get the symbol
name = args.name

symbol, url = get_alphaspread_symbol_url(name)

# Analyze the symbol
analysis = analyze_url(url, symbol)

# Print the analysis
print(analysis)

# UGI, ARBOR
