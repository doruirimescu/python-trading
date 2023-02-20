CREATE DATABASE IF NOT EXISTS trading;
USE trading;


SET time_zone = '+00:00';

CREATE TABLE IF NOT EXISTS swaps(
    id int NOT NULL AUTO_INCREMENT PRIMARY KEY,
    date_added DATE,
    instrument VARCHAR(20) NOT NULL,
    accumulated_swap DECIMAL(10,2) NOT NULL
);

-- All net profits in microlots
CREATE TABLE IF NOT EXISTS hedge_monitor(
    date_open DATE NOT NULL,
    instrument_1_symbol VARCHAR(20) NOT NULL,
    instrument_2_symbol VARCHAR(20) NOT NULL,
    instrument_1_open_price DECIMAL (10,5) NOT NULL,
    instrument_2_open_price DECIMAL (10,5) NOT NULL,
    instrument_1_net_profits DECIMAL (10,2) NOT NULL,
    instrument_2_net_profits DECIMAL (10,2) NOT NULL,
    PRIMARY KEY(date_open, instrument_1_symbol, instrument_2_symbol, instrument_1_open_price, instrument_2_open_price)
);

CREATE TABLE IF NOT EXISTS contract_value(
    symbol VARCHAR(20) NOT NULL,
    contract_value DECIMAL (10,2) NOT NULL,
    PRIMARY KEY(symbol)
);

CREATE TABLE IF NOT EXISTS margin_level(
    id int NOT NULL PRIMARY KEY,
    balance DECIMAL (10,2) NOT NULL,
    margin DECIMAL (10,2) NOT NULL,
    equity DECIMAL (10,2) NOT NULL,
    margin_free DECIMAL (10,2) NOT NULL,
    margin_level DECIMAL (10,2) NOT NULL,
    stock_value DECIMAL (10,2) NOT NULL
);

CREATE TABLE IF NOT EXISTS hedged_profit(
    trade_name VARCHAR(100) NOT NULL,
    net_profit DECIMAL (10,2) NOT NULL
);

-- CREATE TABLE IF NOT EXISTS open_trades(
--     id int NOT NULL AUTO_INCREMENT PRIMARY KEY,
--     description VARCHAR(20) NOT NULL,
--     net_profit DECIMAL (10,2) NOT NULL,
-- );
