"""fee_revenue: congestion and airport fee dollars by month and mode (Q14)."""

from datetime import date

from factories import agg_table, write_agg

from pipeline import metrics

DEC24, MAR = date(2024, 12, 1), date(2025, 3, 1)


def test_fee_revenue(data_dir):
    write_agg("agg_fees_month", agg_table("agg_fees_month", [
        {"month": MAR, "mode": "uber", "cbd_fee": 1_500.0, "trips_with_cbd_fee": 1_000,
         "congestion_surcharge": 2_750.0, "airport_fee": 50.0},
        {"month": MAR, "mode": "yellow", "cbd_fee": 750.0, "trips_with_cbd_fee": 1_000,
         "congestion_surcharge": 2_500.0, "airport_fee": 175.0},
        {"month": DEC24, "mode": "uber", "cbd_fee": 0.0, "trips_with_cbd_fee": 0,
         "congestion_surcharge": 2_750.0, "airport_fee": 0.0},
    ]))
    table = metrics.run("fee_revenue")
    assert table.column_names == ["month", "mode", "cbd_fee", "trips_with_cbd_fee", "congestion_surcharge",
                                  "airport_fee"]
    # One agg_fees_month row per month × mode, so the sums are the stored values, in contract order.
    # December 2024 predates the toll: cbd_fee 0.
    assert table.to_pylist() == [
        {"month": DEC24, "mode": "uber", "cbd_fee": 0.0, "trips_with_cbd_fee": 0,
         "congestion_surcharge": 2_750.0, "airport_fee": 0.0},
        {"month": MAR, "mode": "uber", "cbd_fee": 1_500.0, "trips_with_cbd_fee": 1_000,
         "congestion_surcharge": 2_750.0, "airport_fee": 50.0},
        {"month": MAR, "mode": "yellow", "cbd_fee": 750.0, "trips_with_cbd_fee": 1_000,
         "congestion_surcharge": 2_500.0, "airport_fee": 175.0},
    ]
