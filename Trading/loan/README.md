# Loan management tool with REST API
You will need to first create a loan.json file described in the section below. This is the ground truth and the main source of data for this application.

## JSON format

```json
{
    "total": 100000,
    "history":[
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
                "cost": 3.5
            }
    ]
}
```
#### Key Fields

- `total`: The total loan amount to be repaid.
- `history`: An array of transaction records.

#### Schema Details

##### `total`
- **Type**: Number
- **Description**: Represents the overall amount of the loan to be repaid.

##### `history`
- **Type**: Array of Objects
- **Description**: Contains a list of individual repayment transaction records.

#### Transaction Record Schema

Each object in the `history` array represents a single transaction and contains the following fields:

1. **date**
   - **Type**: String
   - **Format**: YYYY-MM-DD
   - **Description**: The date when the transaction occurred.

2. **principal**
   - **Type**: Number
   - **Description**: The amount of the loan principal that was paid in this transaction.

3. **interest**
   - **Type**: Number
   - **Description**: The amount of interest paid in this transaction.

4. **cost**
   - **Type**: Number
   - **Description**: Any additional costs incurred in this transaction.


Visualize your loan repayment progress 
