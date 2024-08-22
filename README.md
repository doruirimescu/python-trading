# Python Financial Framework
![example workflow](https://github.com/doruirimescu/PythonTrading/actions/workflows/main.yml/badge.svg?branch=master) 
[![Python 3.10](https://img.shields.io/badge/python-3.10-blue.svg)]()

### A multi-tool trading, investing, and asset management platform
- Trading instruments (seamlessly connecting with XTB brokers)
- Stock monitoring and analysis (fusing data from different vendors, such as XTB, yahoo finance, alphaspread)
- Loan monitoring and analysis, for keeping track of your loans, as well as informed decision making between a loan an an investment
- Investment monitoring and analysis, for keeping track of your investments and other assets (precious metals)
- Symbols and constants management (investing.com, alphaspread, XTB). yfinance coming soon

This framework is made to work with an [XTB client](https://github.com/doruirimescu/XTBApi). However, you can implement your own platform's client and use it with [my wrapper](https://github.com/doruirimescu/python-trading/tree/master/Trading/live/client)

First step after cloning: `./install_requirements.sh`

Second step: read [this](https://github.com/doruirimescu/python-trading/tree/master/Trading/live/scripts#readme)

### Navigation
This repo is **HUGE**, and you will probably not need 90% of the things in here. 

There is a lot of code that deals with data from [xAPI](http://developers.xstore.pro/documentation/). You can make a demo account [here](https://www.xtb.com/cy) and try the more advanced features of this repo, but most of the software here is self-contained.

* Loan management [here](https://github.com/doruirimescu/python-trading/blob/master/Trading/loan/README.md)
* Investment and precious metal model [here](https://github.com/doruirimescu/python-trading/blob/master/Trading/model/investment.py)
* Precious metal investment tracking [here](https://github.com/doruirimescu/python-trading/tree/master/Trading/investment)
* Alerts [here](https://github.com/doruirimescu/python-trading/tree/master/Trading/live/alert)
* Alphaspread cli for stock analysis [here](https://github.com/doruirimescu/python-trading/tree/master/Trading/stock/alphaspread)
* Rest api [here](https://github.com/doruirimescu/python-trading/tree/master/Trading/api)
* Daily nasdaq 100 analysis with alphaspread [here](https://github.com/doruirimescu/python-trading/tree/master/Trading/generated)
* Dividend growth sustainability analysis [here](https://github.com/doruirimescu/python-trading/blob/master/Trading/stock/yfinance/dividend_sustainability.py)
* Symbols management, this needs to be frameworked [here](https://github.com/doruirimescu/python-trading/tree/master/Trading/symbols)
* Dealing with time [here](https://github.com/doruirimescu/python-trading/blob/master/Trading/utils/time.py). Always use these helpers.
* Complex logical expressions: [criterion](https://github.com/doruirimescu/python-trading/blob/master/Trading/utils/criterion/readme.md)

Whenever something really important comes up, it is eventually extracted as a standalone repo, and becomes an external dependency such as:
* [Stateful Data Processor](https://github.com/doruirimescu/stateful-data-processor/tree/master)
* [Exception With Retry](https://github.com/doruirimescu/exception-with-retry)

### Papers
Yes, I write papers. Some are more mathematical, some are light reads, other are unpublished manuscripts kept in a folder in my room.
* [Light read] A method for classifying and assessing trades based on exit and entry conditions [here](https://github.com/doruirimescu/python-trading/blob/master/papers/bounded_unbounded_trades.md)
* [Heavy maths] Optimal risk management, basically an independent derivation of Kelly's criterion [here](https://github.com/doruirimescu/python-trading/blob/master/papers/Optimal%20risk%20management.pdf)
* [Trading strategy] A Quantitative Approach to Selecting Stocks in a Ranging Market [here](https://github.com/doruirimescu/python-trading/blob/master/papers/ranging_market.md)
* [My magnum opum strategy] [This](https://github.com/doruirimescu/python-trading/blob/master/papers/mean_reversion_strategy.md) is a work in progress, residing mostly in my head and on scattered papers


# Pipeline structure
![automation_flow drawio](papers/automation-flow.png)

The main pipeline consists of two parts: main and other workflows.

# Snapshots
![Selection_2471](https://github.com/user-attachments/assets/df0d6600-672d-4c86-9c74-d8af61555a09)
![image](https://github.com/user-attachments/assets/ff348a67-4359-47c1-9fdd-9134f11317ea)
![Selection_2473](https://github.com/user-attachments/assets/b7a21e49-9031-47bb-ab77-4ad5c961ccf7)
![image](https://github.com/user-attachments/assets/114cd89a-9cd9-429f-ab79-60d17232a75b)
![image](https://github.com/user-attachments/assets/a18bed1b-6e85-4a3c-802e-ebf0ef78c633)
![image](https://github.com/user-attachments/assets/7153cc7f-dffc-4a18-bc34-7da47cdd2528)
