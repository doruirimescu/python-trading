from Trading.symbols.constants import ALPHASPREAD_URL_DICT, ALPHASPREAD_URL_PATH

FINE_SYMBOLS = ["GOOGC", "VOW1", "MAERSKB", ""]

total_count = len(ALPHASPREAD_URL_DICT)
null_count = 0
possibly_wrong_count = 0

for symbol in ALPHASPREAD_URL_DICT:
    if symbol in FINE_SYMBOLS:
        continue
    if ALPHASPREAD_URL_DICT[symbol] is None:
        null_count += 1
        continue
    if symbol.lower() not in ALPHASPREAD_URL_DICT[symbol]:
        possibly_wrong_count += 1
        print(symbol)
fine = total_count - null_count - possibly_wrong_count

def get_percentage(count):
    return round(count/total_count * 100, 1)


print("What\tCount\tPercentage")
print("-----\t-----\t----------")
print(f"Null\t{null_count}\t{get_percentage(null_count)}%")
print(f"Wrong\t{possibly_wrong_count}\t{get_percentage(possibly_wrong_count)}%")
print(f"Fine\t{fine}\t{get_percentage(fine)}%")
print(f"Total\t{total_count}\t100%")
