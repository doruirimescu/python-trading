# Loan management tool with REST API

## 1. Loan repayment monitoring

Monitor and analyze the status of your loan repayment!

You will need to first create a loan.json file described in the section below. This is the ground truth and the main source of data for this application. You will need to add data manually (by editing the json), or via the API POST endpoint `/loan/history`.

The json format is described [here](./json_format.md).

Visualize your loan repayment progress by connecting Grafana to the [REST API](../api).

You can use my Grafana [dashboard template](./grafana-loan.json), or you can make your own.

Here is one example (concrete numbers are blurred out in paint):
![Selection_1514](https://github.com/doruirimescu/python-trading/assets/7363000/86b2e563-4219-42aa-b61e-014c441563b4)

## 2. Loan vs investment analysis
Should I repay my loan, or should I invest my cash this month?

Setup the constants in [this script](https://github.com/doruirimescu/python-trading/blob/af2b89028dd09c2c0a13f2fd9d994269ed52a6a8/Trading/loan/loan_vs_investment.py#L178).

Then run the script find out.
