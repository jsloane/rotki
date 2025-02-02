from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlite3 import Connection

    from rotkehlchen.db.dbhandler import DBHandler


def _create_new_tables(conn: 'Connection') -> None:
    """Create new tables added at this upgrade

    Should be called at the end of the upgrade as it depends on the changes
    done to the transactions table
    """
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS ethtx_receipts (
    tx_hash BLOB NOT NULL PRIMARY KEY,
    contract_address TEXT, /* can be null */
    status INTEGER NOT NULL CHECK (status IN (0, 1)),
    type INTEGER NOT NULL,
    FOREIGN KEY(tx_hash) REFERENCES ethereum_transactions(tx_hash) ON DELETE CASCADE ON UPDATE CASCADE
    );""")  # noqa: E501
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS ethtx_receipt_logs (
    tx_hash BLOB NOT NULL,
    log_index INTEGER NOT NULL,
    data BLOB NOT NULL,
    address TEXT NOT NULL,
    removed INTEGER NOT NULL CHECK (removed IN (0, 1)),
    FOREIGN KEY(tx_hash) REFERENCES ethtx_receipts(tx_hash) ON DELETE CASCADE ON UPDATE CASCADE,
    PRIMARY KEY(tx_hash, log_index)
    );""")
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS ethtx_receipt_log_topics (
    tx_hash BLOB NOT NULL,
    log_index INTEGER NOT NULL,
    topic BLOB NOT NULL,
    topic_index INTEGER NOT NULL,
    FOREIGN KEY(tx_hash, log_index) REFERENCES ethtx_receipt_logs(tx_hash, log_index) ON DELETE CASCADE ON UPDATE CASCADE,
    PRIMARY KEY(tx_hash, log_index, topic_index)
    );""")  # noqa: E501


def upgrade_v28_to_v29(db: 'DBHandler') -> None:
    """Upgrades the DB from v28 to v29

    - Alters the primary key of blockchain accounts to be blockchain type + account
    - Alters the xpub_mappings to reference the new blockchain accounts
    - Alters the ethereum transactions table to have tx_hash as primary key
    """
    cursor = db.conn.cursor()
    query = cursor.execute('SELECT blockchain, account, label FROM blockchain_accounts;')
    accounts_data = query.fetchall()
    query = cursor.execute('SELECT address, xpub, derivation_path, account_index, derived_index FROM xpub_mappings;')  # noqa: E501
    xpub_mappings_data = query.fetchall()
    query = cursor.execute('SELECT tx_hash, timestamp, block_number, from_address, to_address, value, gas, gas_price, gas_used, input_data, nonce FROM ethereum_transactions;')  # noqa: E501
    transactions_data = [entry for entry in query if entry[10] >= 0]  # non-internal
    cursor.execute('DROP TABLE IF EXISTS blockchain_accounts;')
    cursor.execute('DROP TABLE IF EXISTS xpub_mappings;')
    cursor.execute('DROP TABLE IF EXISTS ethereum_transactions;')
    # create the new tables and insert all values into it
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS blockchain_accounts (
    blockchain VARCHAR[24] NOT NULL,
    account TEXT NOT NULL,
    label TEXT,
    PRIMARY KEY (blockchain, account)
    );
    """)
    cursor.executemany(
        'INSERT INTO blockchain_accounts(blockchain, account, label) VALUES(?, ?, ?);',
        accounts_data,
    )
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS xpub_mappings (
    address TEXT NOT NULL,
    xpub TEXT NOT NULL,
    derivation_path TEXT NOT NULL,
    account_index INTEGER,
    derived_index INTEGER,
    blockchain TEXT GENERATED ALWAYS AS ("BTC") VIRTUAL,
    FOREIGN KEY(blockchain, address) REFERENCES blockchain_accounts(blockchain, account) ON DELETE CASCADE
    FOREIGN KEY(xpub, derivation_path) REFERENCES xpubs(xpub, derivation_path) ON DELETE CASCADE
    PRIMARY KEY (address, xpub, derivation_path)
    );
    """)  # noqa: E501
    cursor.executemany(
        'INSERT INTO xpub_mappings(address, xpub, derivation_path, account_index, derived_index) '
        'VALUES(?, ?, ?, ?, ?);',
        xpub_mappings_data,
    )
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ethereum_transactions (
    tx_hash BLOB NOT NULL PRIMARY KEY,
    timestamp INTEGER NOT NULL,
    block_number INTEGER NOT NULL,
    from_address TEXT NOT NULL,
    to_address TEXT,
    value TEXT NOT NULL,
    gas TEXT NOT NULL,
    gas_price TEXT NOT NULL,
    gas_used TEXT NOT NULL,
    input_data BLOB NOT NULL,
    nonce INTEGER NOT NULL
    );
    """)  # noqa: E501
    cursor.executemany(
        'INSERT INTO ethereum_transactions(tx_hash, timestamp, block_number, from_address, to_address, value, gas, gas_price, gas_used, input_data, nonce) '  # noqa: E501
        'VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);',
        transactions_data,
    )

    _create_new_tables(db.conn)
    db.conn.commit()
