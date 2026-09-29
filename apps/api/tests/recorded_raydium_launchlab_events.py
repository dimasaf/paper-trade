"""Recorded Raydium LaunchLab program activity used without network access."""

from typing import Any

RAYDIUM_LAUNCHLAB_PROGRAM_ID = "LanMV9sAd7wArD4vJFi2qDdfnVhFxYSUg6eADduJ3uj"
RAYDIUM_MINT_ADDRESS = "JEKNVnkbo3jma5nREBBJCDoXFVeKkD56V3xKrvRmWxFG"
RAYDIUM_CREATOR_ADDRESS = "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1"
RAYDIUM_POOL_ADDRESS = "27G8MtK7VtTcCHkpASjSDdkWWYfoqT6ggEuKidVJidD4"


def recorded_raydium_launchlab_program_activity() -> list[dict[str, Any]]:
    """Creation, migration/pool creation, duplicate, malformed, and processed records."""

    creation = {
        "program_id": RAYDIUM_LAUNCHLAB_PROGRAM_ID,
        "activity": "creation",
        "signature": "recorded-raydium-launchlab-create-0001",
        "slot": 314159300,
        "block_time": "2026-09-28T10:00:00Z",
        "observed_at": "2026-09-28T10:00:04Z",
        "commitment": "confirmed",
        "mint": RAYDIUM_MINT_ADDRESS,
        "creator": RAYDIUM_CREATOR_ADDRESS,
        "name": "Recorded Raydium Token",
        "symbol": "RRAY",
    }
    migration = {
        "program_id": RAYDIUM_LAUNCHLAB_PROGRAM_ID,
        "activity": "migration",
        "signature": "recorded-raydium-launchlab-migrate-0002",
        "slot": 314159301,
        "block_time": "2026-09-28T10:15:00Z",
        "observed_at": "2026-09-28T10:15:03Z",
        "commitment": "confirmed",
        "mint": RAYDIUM_MINT_ADDRESS,
        "creator": RAYDIUM_CREATOR_ADDRESS,
        "pool": RAYDIUM_POOL_ADDRESS,
    }
    return [
        creation,
        dict(creation),
        migration,
        {**migration, "activity": "pool_creation"},
        {**creation, "program_id": "not-a-documented-launchlab-program"},
        {
            **creation,
            "signature": "recorded-raydium-launchlab-processed-0003",
            "commitment": "processed",
        },
    ]
