## JSON format

```json
{
    "total": 100000,
    "interest_rate": 3.97,
    "monthly_installment": 454.17,
    "history": [
        {
            "date": "2022-05-02",
            "principal": 100.99,
            "interest": 47.24,
            "cost": 2.5
        },
        {
            "date": "2022-06-02",
            "principal": 124.01,
            "interest": 50.21,
            "cost": 3.5,
            "interest_rate": 4.25
        }
    ]
}
```

#### Key Fields

- `total`: The original total principal of the loan.
- `interest_rate`: Global annual interest rate (%). Used as fallback when no entry-level rate is set.
- `monthly_installment`: Fixed monthly installment (€). Optional, used by simulations.
- `history`: An array of transaction records.

#### Transaction Record Schema

Each object in the `history` array represents a single transaction:

1. **date**
   - **Type**: String
   - **Format**: YYYY-MM-DD
   - **Description**: The date when the transaction occurred.

2. **principal**
   - **Type**: Number
   - **Description**: The amount of the loan principal paid in this transaction (€).

3. **interest**
   - **Type**: Number
   - **Description**: The interest paid in this transaction (€). Set to `0` for lump-sum principal payments.

4. **cost**
   - **Type**: Number
   - **Description**: Additional bank fees or transaction costs (€). Set to `0` if none.

5. **interest_rate** *(optional)*
   - **Type**: Number
   - **Description**: Annual interest rate in effect at the time of this transaction (%). When present, this overrides the global `interest_rate` for any forward-looking calculations (e.g. upcoming monthly interest). The most recent entry that has this field set is used. Useful for tracking variable-rate mortgages where the rate changes over time.
