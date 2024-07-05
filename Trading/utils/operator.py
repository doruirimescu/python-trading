import operator

# Dictionary mapping operator functions to their string representations
OPERATOR_TO_SYMBOL = {
    operator.lt: "<",
    operator.le: "<=",
    operator.eq: "==",
    operator.ne: "!=",
    operator.ge: ">=",
    operator.gt: ">",
    operator.add: "+",
    operator.sub: "-",
    operator.mul: "*",
    operator.truediv: "/",
    operator.floordiv: "//",
    operator.mod: "%",
    operator.pow: "**",
    operator.and_: "&",
    operator.or_: "|",
    operator.xor: "^",
    operator.not_: "not",
    operator.inv: "~"
}

# Map of comparator names to actual functions
NAME_TO_OPERATOR = {
    'gt': operator.gt,
    'lt': operator.lt,
    'eq': operator.eq,
    'ne': operator.ne,
    'ge': operator.ge,
    'le': operator.le,
}
