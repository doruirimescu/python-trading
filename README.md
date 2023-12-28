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


# Pipeline structure
The main pipeline consists of two parts: main and other workflows
## Main
Consists of:
1. `build-and-push`: generates the docker image and pushes it to container registry, with branch name as a tag
2. `test`: pulls this docker image, and runs pytests
## Other workflows
- TBD
