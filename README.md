# CoinMarkecap Scraper

### Overview

- Get token addresses across various blockchain networks.
- Get network information such as:
  - Chain Ids
  - Native Currencies

---

### Setup

1. Clone git repository: `https://github.com/Primitive-Coding/CryptoMarketcapScraper.git`

2. Install the projects requirements with `pip install -r requirements.txt`

3. Setup `config.json` file.

```
    {
        "data_export_path": "D:\\PATH TO PROJECT DIRECTORY\\CoinMarketCapScraper"
    }
```

---

### Instructions

- Create a class instance.
- The program mainly interfaces with the local database found in `crypto.db`.
  - If the information is not found in the database, it will scrape it using the `CoinMarketcapScraper()` class.
  - Once it is scraped, it will be saved to the database.

```
    d = Database()
```

###### Token Addresses

- Below is how to retrieve a token address.
- They can be searched by their chain id, or network name (network's are named according to CoinMarketcap API).

```
    # Search by chain ID.
    address = d.get_token_address("WETH", 1, By.ID)

    # Output
    0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2

    # Search by network.
    address = d.get_token_address("WETH", "Ethereum", By.Network)

    # Output
    0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2
```

- Below is how to query all known addresses for a token.

```
    addresses = d.get_token_addresses("RNDR")

    # Output
    {
        'Ethereum': '0x6De037ef9aD2725EB40118Bb1702EBb27e4Aeb24',
        'Polygon': '0x61299774020dA444Af134c82fa83E3810b309991',
        'Solana': 'rndrizKT3MK1iimdxRdWabcF7Zg7AR5T4nud4EkHBof'
    }
```

###### Network Info

- Below is how to query network info.

```
    # Ethereum Example
    info = d.get_network_info("Ethereum")

    # Output
    native      ETH
    chain_id      1

    ---
    # Arbitrum One Example
    info = d.get_network_info("Arbitrum")

    # Output
    native        ETH
    chain_id    42161


    ---
    # Polygon Example
    info = d.get_network_info("Polygon")

    # Output
    native      MATIC
    chain_id      137
```
