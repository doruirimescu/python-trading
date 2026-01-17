
# Sustainable Leverage in Global Equity ETFs

## 1. Introduction

This paper explores the mechanics and constraints of applying leverage to a diversified global equity exchange-traded fund (ETF), specifically the **Vanguard FTSE All-World UCITS ETF (FWRA)**.

The primary objective of this section is to determine the **Maximum Sustainable Leverage Ratio** ($\lambda_{\max}$). This is defined as the maximum leverage an investor can utilize at inception such that the portfolio survives a specified market drawdown without triggering a forced liquidation (margin call) by the broker.

---

## 2. Definitions of Variables

To maintain precision, we define the following variables:

- $E_0$: Initial Equity (cash invested by the investor).
- $A_0$: Initial Total Asset Value (equity + borrowed funds).
- $L_0$: Initial Loan Value (borrowed funds), where
  
$$
L_0 = A_0 - E_0
$$

- $\lambda$: Leverage ratio at inception, defined as

$$
\lambda = \frac{A_0}{E_0}
$$

- $D$: Market drawdown percentage (expressed as a decimal, e.g., $0.50$ for 50%).
- $MM$: Maintenance margin requirement.
- $A_t$: Asset value after drawdown $D$.
- $E_t$: Equity value after drawdown $D$.

---

## 3. Core Assumptions

For the purpose of this initial calculation (the **Survival Stress Test**), the following assumptions are made:

### Broker & Margin Rules
- The broker is **Interactive Brokers (IBKR)**.
- A Regulation T margin account or standard IBKR retail margin account is assumed.
- The maintenance margin ($MM$) for a broad index ETF such as FWRA is assumed to be **25%** ($0.25$).

> While portfolio margin may allow lower requirements, 25% represents the regulatory floor and is used to assess hard liquidation risk.

### Market Stress Scenario
- A **50% instantaneous market drawdown** is assumed ($D = 0.50$), comparable to the Global Financial Crisis of 2008.

### Loan Stability
- The loan amount $L_0$ remains constant during the drawdown.
- Interest accrual during the crash is assumed to be negligible.

### Survival Condition
- The portfolio survives if post-drawdown equity satisfies:
  
$$
E_t \geq MM \times A_t
$$

---

## 4. Derivation of the Maximum Sustainable Leverage

The objective is to find the maximum $\lambda$ such that the maintenance margin constraint is satisfied after a drawdown.

### Step 1: Post-Drawdown Portfolio Values

After a market drawdown of $D$:

$$
A_t = A_0 (1 - D)
$$

The loan remains unchanged:

$$
L_0 = A_0 \left(1 - \frac{1}{\lambda}\right)
$$

Equity after the drawdown is:

$$
E_t = A_t - L_0
$$

Substituting:

$$
E_t = A_0(1 - D) - A_0\left(1 - \frac{1}{\lambda}\right)
$$

---

### Step 2: Maintenance Margin Constraint

The broker requires:

$$
E_t \geq MM \times A_t
$$

Substitute expressions for $E_t$ and $A_t$:

$$
A_0(1 - D) - A_0\left(1 - \frac{1}{\lambda}\right) \geq MM \times A_0(1 - D)
$$

Divide both sides by $A_0$:

$$
(1 - D) - \left(1 - \frac{1}{\lambda}\right) \geq MM(1 - D)
$$

---

### Step 3: Solving for $\lambda$

Rearranging terms:

$$
\frac{1}{\lambda} \geq 1 - (1 - D)(1 - MM)
$$

Inverting both sides:

$$
\lambda \leq \frac{1}{1 - (1 - D)(1 - MM)}
$$

---

## 5. Numerical Example: 50% Drawdown Scenario

Using the specified assumptions:

- $D = 0.50$
- $MM = 0.25$

$$
\lambda_{\max} = \frac{1}{1 - (1 - 0.50)(1 - 0.25)}
$$

$$
\lambda_{\max} = \frac{1}{1 - (0.50)(0.75)}
$$

$$
\lambda_{\max} = \frac{1}{1 - 0.375}
$$

$$
\lambda_{\max} = \frac{1}{0.625}
$$

$$
\lambda_{\max} = 1.6
$$

---

## 6. Conclusion

To survive a **50% market drawdown** on a diversified global equity ETF with a **25% maintenance margin requirement**, the maximum sustainable initial leverage ratio is:

$$
\boxed{\lambda_{\max} = 1.6}
$$

This implies that for every **$10,000** of investor equity, the maximum position size is **$16,000**, financed with **$6,000** of borrowed capital.

This leverage level represents a **hard upper bound** under conservative regulatory assumptions and should be interpreted as a survival threshold rather than an optimal leverage choice.
