import type { Instrument } from "./api";


export function MarketCatalog({ instruments }: { instruments: Instrument[] }) {
  const activeInstruments = instruments.filter(
    (instrument) =>
      instrument.is_active &&
      instrument.base_asset.is_active &&
      instrument.quote_asset.is_active,
  );

  return (
    <section className="panel market-panel">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">Рынок</span>
          <h2>Торговые инструменты</h2>
        </div>
        <span className="count-badge">{activeInstruments.length}</span>
      </div>

      {activeInstruments.length === 0 ? (
        <p className="muted">Активные торговые инструменты пока не добавлены.</p>
      ) : (
        <div className="instrument-grid">
          {activeInstruments.map((instrument) => (
            <article className="instrument-card" key={instrument.id}>
              <strong>
                {instrument.base_asset.symbol}/{instrument.quote_asset.symbol}
              </strong>
              <span>
                {instrument.base_asset.name} · {instrument.quote_asset.name}
              </span>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
