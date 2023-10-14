import numpy
from decimal import *


class Loan:
    def __init__(self, principal, interest_rate, fixed_monthly_installment):
        self.principal = principal
        self.interest_rate = interest_rate
        self.total_interest_paid = 0
        self.fixed_monthly_installment = fixed_monthly_installment

    def repay(self, yearly_payment):
        interest = self.get_yearly_interest()
        self.total_interest_paid += interest
        principal_paid_this_year = yearly_payment - interest
        self.principal -= principal_paid_this_year

        self.interest_rate = self.interest_rate

    def is_enough_payment(self, yearly_payment):
        return (
            yearly_payment
            >= self.get_yearly_interest() + 12 * self.fixed_monthly_installment
        )

    def get_yearly_interest(self):
        return self.interest_rate * self.principal

    def is_done(self):
        return self.principal <= 0


class Investment:
    def __init__(self, annual_return_rate):
        self.total_invested = 0
        self.gains = 0
        self.annual_return_rate = annual_return_rate

    def invest(self, amount, current_year, n_years):
        self.total_invested += amount

        future_multiplier = (1 + self.annual_return_rate) ** (
            (n_years - current_year - 1)
        )

        self.gains += amount * future_multiplier

    def get_total_invested(self):
        return self.total_invested

    def get_gains(self):
        return self.gains

    def get_total_worth(self):
        return self.gains + self.total_invested


def plot(
    p_range, total_worth_list, principal, n_years, investment_return, yearly_salary
):
    import matplotlib.pyplot as plt

    plt.plot(p_range, total_worth_list)
    plt.grid()
    plt.title(
        f"Total worth (thousands of eur) vs. percentage of salary that goes to loan\n"
        f"For a {n_years}-year loan of {principal} eur at {round(IR*100,2)}% interest rate\n"
        f"Assuming a {round(investment_return*100, 2)}% annual return rate\n"
        f"Given a {yearly_salary} eur yearly salary"
    )

    xlab = "Percentage of salary that goes to loan"
    ylab = "Total worth (thousands of eur)"
    plt.xlabel(xlab)
    plt.ylabel(ylab)
    plt.show()


def _simulate_percentage(
    years,
    percentage,
    principal,
    interest_rate,
    fixed_monthly_installment,
    investment_return,
    yearly_salary,
):
    l = Loan(principal, interest_rate, fixed_monthly_installment)
    i = Investment(investment_return)

    if not l.is_enough_payment(yearly_salary * percentage):
        # print(f"Percentage {percentage} infeasible")
        return

    for year in range(years):
        yearly_payment = 0
        yearly_investment = 0
        if not l.is_done():
            yearly_payment = yearly_salary * percentage
            if yearly_payment > l.principal:
                yearly_payment = l.principal + l.get_yearly_interest()

            yearly_investment = yearly_salary - yearly_payment
        else:
            yearly_investment = yearly_salary
        l.repay(yearly_payment)
        i.invest(yearly_investment, year, years)

    total_worth = i.get_total_worth()

    if not l.is_done():
        total_worth -= l.principal + l.total_interest_paid
    return total_worth

def perform_simulation(
    principal: int,
    interest_rate: float,
    fixed_month_installement: int,
    investment_return: float,
    yearly_salary: int,
    n_years: int,
    should_plot: bool = False,
):
    infeasible_ps = list()
    total_worth_list = list()
    P_RANGE_START = 0.05
    P_RANGE_FINISH = 1.0
    P_STEP = 0.01
    p_range = numpy.arange(P_RANGE_START, P_RANGE_FINISH, P_STEP)

    for p in p_range:
        print(p)
        result = _simulate_percentage(
            n_years,
            p,
            principal,
            interest_rate,
            fixed_month_installement,
            investment_return,
            yearly_salary,
        )
        if result is None:
            infeasible_ps.append(p)
        else:
            total_worth_list.append(result / 1000)

    p_range = list(set(list(p_range)) - set(infeasible_ps))
    p_range = sorted(p_range)
    # plot total_worth_list vs p
    p_range = [p * 100 for p in p_range]
    if should_plot:
        plot(
            p_range, total_worth_list, principal, n_years, investment_return, yearly_salary
        )
    # get max and min total worth
    max_total_worth = max(total_worth_list)
    min_total_worth = min(total_worth_list)
    # get max and min p
    max_p = p_range[total_worth_list.index(max_total_worth)]
    min_p = p_range[total_worth_list.index(min_total_worth)]
    return {
        "max_p": round(max_p, 2),
        "max_total_worth": round(max_total_worth, 2),
        "min_p": round(min_p, 2),
        "min_total_worth": round(min_total_worth, 2),
        "max_vs_min_total_worth": round(100 * max_total_worth / min_total_worth, 2),
        "p_range": p_range,
        "total_worth_list": total_worth_list,
    }

PRINCIPAL = 200000
IR = 5.5 / 100
FIXED_MONTHLY_INSTALLMENT = 450


INVESTMENT_RETURN = round(7 / 100, 2)

N_YEARS = 10
N_MONTHS = 12 * N_YEARS

MONTHLY_SALARY = 3500
YEARLY_SALARY = 12 * MONTHLY_SALARY

# perform_simulation(
#     PRINCIPAL,
#     IR,
#     FIXED_MONTHLY_INSTALLMENT,
#     INVESTMENT_RETURN,
#     YEARLY_SALARY,
#     N_YEARS,
# )
