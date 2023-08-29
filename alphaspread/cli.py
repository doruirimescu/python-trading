# add cli parser for the symbol
import argparse
from alphaspread import analyze_url
from google import get_first_google_result

# Create a parser object
parser = argparse.ArgumentParser(description="Get the symbol and url to analyze.")
parser.add_argument("--name", help="The name or symbol of company to analyze.", )

# Parse the arguments
args = parser.parse_args()

# Get the symbol
name = args.name

url = get_first_google_result("alphaspread " + name)
# Strip the symbol as the second last part of the url
symbol = url.split("/")[-2]

# Replace the last part of the url with "summary"
url = url.replace(url.split("/")[-1], "summary")

print(symbol, url)

# Analyze the symbol
analysis = analyze_url(url, symbol)

# Print the analysis
print(analysis)

# UGI, ARBOR
