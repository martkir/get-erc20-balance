from collections import defaultdict
import json
from web3 import Web3
from multicall import Call, Signature
import requests
import os
from dotenv import load_dotenv


load_dotenv()


def fetch_token_balance_naive(wallet_address, token_address, block_number, node_provider_url, api_key):
    balanceof_function = "balanceOf(address)(uint256)"
    balanceof_signature = Signature(balanceof_function)
    block_number_hex = Web3.toHex(primitive=block_number)
    data = balanceof_signature.encode_data([wallet_address]).hex()
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_call",
        "params": [
            {
                "to": token_address,
                "data": "0x" + data,
            },
            block_number_hex,
        ],
        "id": 1,
    }
    headers = {"Content-Type": "application/json", "Accept-Encoding": "gzip"}
    url = f"{node_provider_url}/{api_key}"
    res = requests.post(url, headers=headers, json=payload)
    res_data = res.json()
    balance_encoded_hex = res_data["result"]
    balance_encoded_bytes = Web3.toBytes(hexstr=balance_encoded_hex)
    balance_decoded = Call.decode_output(balance_encoded_bytes, balanceof_signature, returns=None)
    return balance_decoded


def fetch_token_balance_batch(wallet_addresses, token_addresses, block_numbers, node_provider_url, api_key):
    balanceof_function = "balanceOf(address)(uint256)"
    balanceof_signature = Signature(balanceof_function)
    payload_list = []
    for i, (wallet_address, token_address, block_number) in enumerate(
        zip(
            wallet_addresses,
            token_addresses,
            block_numbers,
        )
    ):
        block_number_hex = Web3.toHex(primitive=block_number)
        data = balanceof_signature.encode_data([wallet_address]).hex()
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_call",
            "params": [
                {
                    "to": token_address,
                    "data": "0x" + data,
                },
                block_number_hex,
            ],
            "id": i + 1,
        }
        payload_list.append(payload)
    headers = {"Content-Type": "application/json", "Accept-Encoding": "gzip"}
    url = f"{node_provider_url}/{api_key}"
    res = requests.post(url, headers=headers, json=payload_list)
    res_data_list = res.json()
    balances = []
    for res_data in res_data_list:
        balance_encoded_hex = res_data["result"]
        balance_encoded_bytes = Web3.toBytes(hexstr=balance_encoded_hex)
        balance_decoded = Call.decode_output(balance_encoded_bytes, balanceof_signature, returns=None)
        balances.append(balance_decoded)
    return balances


def load_state_override_code():
    multicall3_metadata_path = "/root/syvedev/populate/eth_balances/metadata/multicall3.json"
    multicall3_metadata = json.load(open(multicall3_metadata_path))
    state_override_code = multicall3_metadata["state_override_code"]
    return state_override_code


def create_multicall_payload_list(block_map, balanceof_signature, aggregate_signature):
    multicall3_address = "0xcA11bde05977b3631167028862bE2a173976CA11"
    state_override_code = load_state_override_code()
    require_success = False
    gas_limit = 50000000
    payload_list = []
    for i, block_number in enumerate(block_map.keys()):
        block_number_hex = Web3.toHex(primitive=block_number)
        call_params_list = []
        for token_address, wallet_address in block_map[block_number]:
            call_params_list.append(
                {
                    "to": token_address,
                    "data": balanceof_signature.encode_data([wallet_address]),
                },
            )
        multicall_params = [
            {
                "to": multicall3_address,
                "data": Web3.toHex(
                    aggregate_signature.encode_data(
                        [
                            require_success,
                            [[c["to"], c["data"]] for c in call_params_list],
                        ]
                    )
                ),
            },
            block_number_hex,
        ]
        if gas_limit:
            multicall_params[0]["gas"] = Web3.toHex(primitive=gas_limit)
        if state_override_code:
            multicall_params.append({multicall3_address: {"code": state_override_code}})
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_call",
            "params": multicall_params,
            "id": i + 1,
        }
        payload_list.append(payload)


def fetch_token_balance_multicall(wallet_addresses, token_addresses, block_numbers, node_provider_url, api_key):
    block_map = defaultdict(lambda: [])
    for block_number, token_address, wallet_address in zip(block_numbers, token_addresses, wallet_addresses):
        block_map[block_number].append((token_address, wallet_address))

    aggregate_function = "tryBlockAndAggregate(bool,(address,bytes)[])(uint256,uint256,(bool,bytes)[])"
    aggregate_signature = Signature(aggregate_function)
    balanceof_function = "balanceOf(address)(uint256)"
    balanceof_signature = Signature(balanceof_function)
    payload_list = create_multicall_payload_list(block_map, aggregate_signature, balanceof_signature)

    headers = {"Content-Type": "application/json", "Accept-Encoding": "gzip"}
    url = f"{node_provider_url}/{api_key}"
    res = requests.post(url, headers=headers, json=payload_list)
    res_data_list = res.json()
    balances = []
    for res_data in res_data_list:
        output_hex = res_data["result"]
        output_bytes = Web3.toBytes(hexstr=output_hex)
        returns = None
        decoded_output = Call.decode_output(
            output_bytes,
            aggregate_signature,
            returns,
        )
        output_pairs = decoded_output[2]
        for flag, balance_encoded in output_pairs:
            balance_decoded = Call.decode_output(balance_encoded, balanceof_signature, returns)
            balances.append(balance_decoded)
    return balances


def fetch_native_balance_multicall(wallet_addresses, block_numbers, node_provider_url, api_key):
    multicall3_address = "0xcA11bde05977b3631167028862bE2a173976CA11"
    state_override_code = load_state_override_code()
    require_success = False
    gas_limit = 50000000
    aggregate_function = "tryBlockAndAggregate(bool,(address,bytes)[])(uint256,uint256,(bool,bytes)[])"
    aggregate_signature = Signature(aggregate_function)
    get_eth_balance_function = "getEthBalance(address)(uint256)"
    get_eth_balance_signature = Signature(get_eth_balance_function)
    payload_list = []

    block_map = defaultdict(lambda: [])
    for block_number, wallet_address in zip(block_numbers, wallet_addresses):
        block_map[block_number].append(wallet_address)

    for i, block_number in enumerate(block_map.keys()):
        block_number_hex = Web3.toHex(primitive=block_number)
        call_params_list = []
        for wallet_address in block_map[block_number]:
            call_params_list.append(
                {
                    "to": multicall3_address,
                    "data": get_eth_balance_signature.encode_data([wallet_address]),
                },
            )
        multicall_params = [
            {
                "to": multicall3_address,
                "data": Web3.toHex(
                    aggregate_signature.encode_data(
                        [
                            require_success,
                            [[c["to"], c["data"]] for c in call_params_list],
                        ]
                    )
                ),
            },
            block_number_hex,
        ]
        if gas_limit:
            multicall_params[0]["gas"] = Web3.toHex(primitive=gas_limit)
        if state_override_code:
            multicall_params.append({multicall3_address: {"code": state_override_code}})
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_call",
            "params": multicall_params,
            "id": i + 1,
        }
        payload_list.append(payload)

    headers = {"Content-Type": "application/json", "Accept-Encoding": "gzip"}
    url = f"{node_provider_url}/{api_key}"
    res = requests.post(url, headers=headers, json=payload_list)
    res_data_list = res.json()
    balances = []
    for res_data in res_data_list:
        output_hex = res_data["result"]
        output_bytes = Web3.toBytes(hexstr=output_hex)
        returns = None
        decoded_output = Call.decode_output(
            output_bytes,
            aggregate_signature,
            returns,
        )
        output_pairs = decoded_output[2]
        for _, balance_encoded in output_pairs:
            balance_decoded = Call.decode_output(balance_encoded, get_eth_balance_signature, returns)
            balances.append(balance_decoded)
    print(json.dumps(balances, indent=4))


def main():
    node_provider_url = "https://eth-mainnet.alchemyapi.io/v2"
    api_key = os.environ["ALCHEMY_API_KEY"]  # Note: You can also use Quicknode

    wallet_address = os.environ["WALLET_ADDRESS"]
    token_address_1 = os.environ["TOKEN_ADDRESS_1"]
    token_address_2 = os.environ["TOKEN_ADDRESS_2"]
    block_number = 17_200_000

    test_naive = False
    test_batch = False
    test_multicall = False
    test_multicall_native = True

    if test_naive:
        balance = fetch_token_balance_naive(
            wallet_address=wallet_address,
            token_address=token_address_1,
            block_number=block_number,
            node_provider_url=node_provider_url,
            api_key=api_key,
        )
        print(json.dumps(balance, indent=4))

    if test_batch:
        balances = fetch_token_balance_batch(
            wallet_addresses=[wallet_address, wallet_address],
            token_addresses=[token_address_1, token_address_2],
            block_numbers=[block_number, block_number],
            node_provider_url=node_provider_url,
            api_key=api_key,
        )
        print(json.dumps(balances, indent=4))

    if test_multicall:
        balances = fetch_token_balance_multicall(
            wallet_addresses=[wallet_address, wallet_address],
            token_addresses=[token_address_1, token_address_2],
            block_numbers=[block_number, block_number],
            node_provider_url=node_provider_url,
            api_key=api_key,
        )

    if test_multicall_native:
        balances = fetch_native_balance_multicall(
            wallet_addresses=[wallet_address],
            block_numbers=[block_number],
            node_provider_url=node_provider_url,
            api_key=api_key,
        )


if __name__ == "__main__":
    main()
