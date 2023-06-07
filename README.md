# get-erc20-balance

This repo outlines the three different approaches for fetching erc20 token balances using a node provider.

The approaches:

- Single JSON-RPC call
- Batching JSON-RPC calls
- Using a multicall contract

## How to test the code?

All logic is in the `run.py` file. A test case is provided for each approach for fetching balances. Just make sure you go over the super short initial setup and requirements first.


## Initial Setup & Requirements

The code is super simple. There is only one requirement you need to install the following python packages:

```
pip install web3
pip install multicall
```

For the code to run you need to also create a `.env` file in the root directory and add the following variables:

```
WALLET_ADDRESS
TOKEN_ADDRESS_1
TOKEN_ADDRESS_2
```


