import logging
import os
from typing import Any, Dict, List, Tuple

import gevent

from rotkehlchen.chain.ethereum.manager import NodeName
from rotkehlchen.chain.ethereum.structures import EthereumTxReceipt, EthereumTxReceiptLog
from rotkehlchen.chain.ethereum.typing import string_to_ethereum_address
from rotkehlchen.db.dbhandler import DBHandler
from rotkehlchen.db.ethtx import DBEthTx
from rotkehlchen.db.filtering import ETHTransactionsFilterQuery
from rotkehlchen.logging import RotkehlchenLogsAdapter
from rotkehlchen.typing import EthereumTransaction, Timestamp
from rotkehlchen.utils.misc import hexstring_to_bytes

NODE_CONNECTION_TIMEOUT = 10

logger = logging.getLogger(__name__)
log = RotkehlchenLogsAdapter(logger)

INFURA_TEST = 'https://mainnet.infura.io/v3/66302b8fb9874614905a3cbe903a0dbb'

ETHERSCAN_AND_INFURA_PARAMS: Tuple[str, List[Tuple]] = ('ethrpc_endpoint,ethereum_manager_connect_at_start, call_order', [  # noqa: E501
    # Query etherscan only
    ('', (), (NodeName.ETHERSCAN,)),
    # For "our own" node querying use infura
    (
        INFURA_TEST,
        (NodeName.OWN,),
        (NodeName.OWN,),
    ),
])

ETHEREUM_TEST_PARAMETERS: Tuple[str, List[Tuple]]
if 'GITHUB_WORKFLOW' in os.environ:
    # For Github actions don't use infura. It seems that connecting to it
    # from Github actions hangs and times out
    ETHEREUM_TEST_PARAMETERS = ('ethrpc_endpoint,ethereum_manager_connect_at_start, call_order', [
        # Query etherscan only
        ('', (), (NodeName.ETHERSCAN,)),
    ])
else:
    # For Travis and local tests also use Infura, works fine
    ETHEREUM_TEST_PARAMETERS = ETHERSCAN_AND_INFURA_PARAMS


def wait_until_all_nodes_connected(
        ethereum_manager_connect_at_start,
        ethereum,
        timeout: int = NODE_CONNECTION_TIMEOUT,
):
    """Wait until all ethereum nodes are connected or until a timeout is hit"""
    connected = [False] * len(ethereum_manager_connect_at_start)
    try:
        with gevent.Timeout(timeout):
            while not all(connected):
                for idx, node_name in enumerate(ethereum_manager_connect_at_start):
                    if node_name in ethereum.web3_mapping:
                        connected[idx] = True

                gevent.sleep(0.1)
    except gevent.Timeout:
        names = [
            str(x) for idx, x in enumerate(ethereum_manager_connect_at_start) if not connected[idx]
        ]
        log.info(
            f'Did not connect to nodes: {",".join(names)} due to '
            f'timeout of {NODE_CONNECTION_TIMEOUT}',
        )


def txreceipt_to_data(receipt: EthereumTxReceipt) -> Dict[str, Any]:
    """Turns it to receipt data as would be returned by web3

    Is here since this would only be done in test. In actual
    serialization snake case would be used.
    """
    data: Dict[str, Any] = {
        'transactionHash': '0x' + receipt.tx_hash.hex(),
        'type': hex(receipt.type),
        'contractAddress': receipt.contract_address,
        'status': int(receipt.status),
        'logs': [],
    }
    for log_entry in receipt.logs:
        log_data = {
            'logIndex': log_entry.log_index,
            'address': log_entry.address,
            'removed': log_entry.removed,
            'data': '0x' + log_entry.data.hex(),
            'topics': [],
        }
        for topic in log_entry.topics:
            log_data['topics'].append('0x' + topic.hex())  # type: ignore

        data['logs'].append(log_data)

    return data


def setup_ethereum_transactions_test(
        database: DBHandler,
        transaction_already_queried: bool,
        one_receipt_in_db: bool = False,
) -> Tuple[List[EthereumTransaction], List[EthereumTxReceipt]]:
    dbethtx = DBEthTx(database)
    tx_hash1 = '0x692f9a6083e905bdeca4f0293f3473d7a287260547f8cbccc38c5cb01591fcda'
    tx_hash1_b = hexstring_to_bytes(tx_hash1)
    transaction1 = EthereumTransaction(
        tx_hash=tx_hash1_b,
        timestamp=Timestamp(1630532276),
        block_number=13142218,
        from_address=string_to_ethereum_address('0x443E1f9b1c866E54e914822B7d3d7165EdB6e9Ea'),
        to_address=string_to_ethereum_address('0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D'),
        value=int(10 * 10**18),
        gas=194928,
        gas_price=int(0.000000204 * 10**18),
        gas_used=136675,
        input_data=hexstring_to_bytes('0x7ff36ab5000000000000000000000000000000000000000000000367469995d0723279510000000000000000000000000000000000000000000000000000000000000080000000000000000000000000443e1f9b1c866e54e914822b7d3d7165edb6e9ea00000000000000000000000000000000000000000000000000000000612ff9b50000000000000000000000000000000000000000000000000000000000000002000000000000000000000000c02aaa39b223fe8d0a0e5c4f27ead9083c756cc20000000000000000000000002a3bff78b79a009976eea096a51a948a3dc00e34'),  # noqa: E501
        nonce=13,
    )
    tx_hash2 = '0x6beab9409a8f3bd11f82081e99e856466a7daf5f04cca173192f79e78ed53a77'
    tx_hash2_b = hexstring_to_bytes(tx_hash2)
    transaction2 = EthereumTransaction(
        tx_hash=tx_hash2_b,
        timestamp=Timestamp(1631013757),
        block_number=13178342,
        from_address=string_to_ethereum_address('0x442068F934BE670aDAb81242C87144a851d56d16'),
        to_address=string_to_ethereum_address('0xEaDD9B69F96140283F9fF75DA5FD33bcF54E6296'),
        value=0,
        gas=77373,
        gas_price=int(0.000000100314697497 * 10**18),
        gas_used=46782,
        input_data=hexstring_to_bytes('0xa9059cbb00000000000000000000000020c8032d4f7d4a380385f87aeadf05bed84504cb000000000000000000000000000000000000000000000000000000003b9deec6'),  # noqa: E501
        nonce=3,
    )
    transactions = [transaction1, transaction2]
    if transaction_already_queried is True:
        dbethtx.add_ethereum_transactions(ethereum_transactions=transactions)
        assert dbethtx.get_ethereum_transactions(ETHTransactionsFilterQuery.make()) == transactions

    expected_receipt1 = EthereumTxReceipt(
        tx_hash=tx_hash1_b,
        contract_address=None,
        status=True,
        type=0,
        logs=[
            EthereumTxReceiptLog(
                log_index=295,
                data=hexstring_to_bytes('0x0000000000000000000000000000000000000000000000008ac7230489e80000'),  # noqa: E501
                address=string_to_ethereum_address('0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2'),
                removed=False,
                topics=[
                    hexstring_to_bytes('0xe1fffcc4923d04b559f4d29a8bfc6cda04eb5b0d3c460751c2402c5c5cc9109c'),  # noqa: E501
                    hexstring_to_bytes('0x0000000000000000000000007a250d5630b4cf539739df2c5dacb4c659f2488d'),  # noqa: E501
                ],
            ), EthereumTxReceiptLog(
                log_index=296,
                data=hexstring_to_bytes('0x0000000000000000000000000000000000000000000000008ac7230489e80000'),  # noqa: E501
                address=string_to_ethereum_address('0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2'),
                removed=False,
                topics=[
                    hexstring_to_bytes('0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'),  # noqa: E501
                    hexstring_to_bytes('0x0000000000000000000000007a250d5630b4cf539739df2c5dacb4c659f2488d'),  # noqa: E501
                    hexstring_to_bytes('0x000000000000000000000000caa004418eb42cdf00cb057b7c9e28f0ffd840a5'),  # noqa: E501
                ],
            ), EthereumTxReceiptLog(
                log_index=297,
                data=hexstring_to_bytes('0x00000000000000000000000000000000000000000000036ba1d53baeeda5ed20'),  # noqa: E501
                address=string_to_ethereum_address('0x2a3bFF78B79A009976EeA096a51A948a3dC00e34'),
                removed=False,
                topics=[
                    hexstring_to_bytes('0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'),  # noqa: E501
                    hexstring_to_bytes('0x000000000000000000000000caa004418eb42cdf00cb057b7c9e28f0ffd840a5'),  # noqa: E501
                    hexstring_to_bytes('0x000000000000000000000000443e1f9b1c866e54e914822b7d3d7165edb6e9ea'),  # noqa: E501
                ],
            ), EthereumTxReceiptLog(
                log_index=298,
                data=hexstring_to_bytes('0x000000000000000000000000000000000000000000007b6ea033189ba7d047e30000000000000000000000000000000000000000000000140bc8194dd0f5e4be'),  # noqa: E501
                address=string_to_ethereum_address('0xcaA004418eB42cdf00cB057b7C9E28f0FfD840a5'),
                removed=False,
                topics=[hexstring_to_bytes('0x1c411e9a96e071241c2f21f7726b17ae89e3cab4c78be50e062b03a9fffbbad1')],  # noqa: E501
            ), EthereumTxReceiptLog(
                log_index=299,
                data=hexstring_to_bytes('0x00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000008ac7230489e8000000000000000000000000000000000000000000000000036ba1d53baeeda5ed200000000000000000000000000000000000000000000000000000000000000000'),  # noqa: E501
                address=string_to_ethereum_address('0xcaA004418eB42cdf00cB057b7C9E28f0FfD840a5'),
                removed=False,
                topics=[
                    hexstring_to_bytes('0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822'),  # noqa: E501
                    hexstring_to_bytes('0x0000000000000000000000007a250d5630b4cf539739df2c5dacb4c659f2488d'),  # noqa: E501
                    hexstring_to_bytes('0x000000000000000000000000443e1f9b1c866e54e914822b7d3d7165edb6e9ea'),  # noqa: E501
                ],
            ),
        ],
    )
    expected_receipt2 = EthereumTxReceipt(
        tx_hash=tx_hash2_b,
        contract_address=None,
        status=True,
        type=2,
        logs=[
            EthereumTxReceiptLog(
                log_index=438,
                data=hexstring_to_bytes('0x000000000000000000000000000000000000000000000000000000003b9deec6'),  # noqa: E501
                address=string_to_ethereum_address('0xEaDD9B69F96140283F9fF75DA5FD33bcF54E6296'),
                removed=False,
                topics=[
                    hexstring_to_bytes('0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'),  # noqa: E501
                    hexstring_to_bytes('0x000000000000000000000000442068f934be670adab81242c87144a851d56d16'),  # noqa: E501
                    hexstring_to_bytes('0x00000000000000000000000020c8032d4f7d4a380385f87aeadf05bed84504cb'),  # noqa: E501
                ],
            ),
        ],
    )

    if one_receipt_in_db:
        dbethtx.add_receipt_data(txreceipt_to_data(expected_receipt1))

    return transactions, [expected_receipt1, expected_receipt2]
