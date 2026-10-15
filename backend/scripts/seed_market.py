from sqlalchemy import select

from backend.app.db.session import SessionLocal
from backend.app.models.asset import Asset
from backend.app.models.instrument import Instrument


ASSETS = (
    ("BTC", "Bitcoin"),
    ("ETH", "Ethereum"),
    ("USD", "US Dollar"),
)

INSTRUMENTS = (
    ("BTC", "USD"),
    ("ETH", "USD"),
)


def main() -> None:
    with SessionLocal() as db:
        assets_by_symbol = {
            asset.symbol: asset for asset in db.scalars(select(Asset)).all()
        }

        for symbol, name in ASSETS:
            asset = assets_by_symbol.get(symbol)
            if asset is None:
                asset = Asset(symbol=symbol, name=name, is_active=True)
                db.add(asset)
                assets_by_symbol[symbol] = asset
            else:
                asset.name = name
                asset.is_active = True

        db.flush()

        existing_pairs = {
            (instrument.base_asset_id, instrument.quote_asset_id)
            for instrument in db.scalars(select(Instrument)).all()
        }
        for base_symbol, quote_symbol in INSTRUMENTS:
            base_asset = assets_by_symbol[base_symbol]
            quote_asset = assets_by_symbol[quote_symbol]
            pair = (base_asset.id, quote_asset.id)
            if pair not in existing_pairs:
                db.add(
                    Instrument(
                        base_asset_id=base_asset.id,
                        quote_asset_id=quote_asset.id,
                        is_active=True,
                    )
                )

        db.commit()
        print("Market catalog is ready: BTC/USD and ETH/USD")


if __name__ == "__main__":
    main()
