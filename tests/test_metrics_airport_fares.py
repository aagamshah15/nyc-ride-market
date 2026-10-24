"""airport_fares: what riders pay from each airport to Manhattan (Q9)."""

from datetime import date

import pytest
from factories import agg_table, write_agg

from pipeline import metrics

FEB, MAR = date(2025, 2, 1), date(2025, 3, 1)


def write_zone_lookup(data_dir):
    (data_dir / "ref").mkdir()
    (data_dir / "ref" / "taxi_zone_lookup.csv").write_text(
        '"LocationID","Borough","Zone","service_zone"\n'
        '1,"EWR","Newark Airport","EWR"\n'
        '7,"Queens","Astoria","Boro Zone"\n'
        '132,"Queens","JFK Airport","Airports"\n'
        '138,"Queens","LaGuardia Airport","Airports"\n'
        '161,"Manhattan","Midtown Center","Yellow Zone"\n'
        '236,"Manhattan","Upper East Side North","Yellow Zone"\n')


def od(month, mode, pu, do, trips, rider_total, fare_base, miles):
    return {"month": month, "mode": mode, "pu_zone": pu, "do_zone": do, "trips_valid": trips,
            "rider_total_ex_tip": rider_total, "fare_base": fare_base, "miles": miles}


def test_airport_fares(data_dir):
    write_zone_lookup(data_dir)
    write_agg("agg_od_month", agg_table("agg_od_month", [
        od(MAR, "uber", 132, 161, 40, 3_000.0, 2_400.0, 720.0),
        od(MAR, "uber", 132, 236, 10, 1_000.0, 600.0, 180.0),
        od(MAR, "yellow", 132, 161, 20, 1_600.0, 1_400.0, 350.0),
        od(MAR, "lyft", 1, 161, 25, 2_500.0, 2_000.0, 500.0),
        od(MAR, "uber", 132, 7, 30, 900.0, 800.0, 200.0),         # to Queens: left out
        od(MAR, "uber", 161, 132, 30, 2_700.0, 2_100.0, 540.0),   # to the airport: left out
        od(FEB, "uber", 132, 161, 99, 9_900.0, 9_000.0, 1_000.0), # another month
    ]))
    table = metrics.run("airport_fares", to_month="2025-03")
    assert table.column_names == ["airport", "mode", "trips", "fare_mean", "fare_base_mean", "fare_per_mile"]
    # JFK uber to Manhattan (161 and 236): 50 trips, rider total 4,000 / 50 = 80, base fare
    # 3,000 / 50 = 60, 3,000 / 900 mi. JFK yellow: 1,600 / 20 = 80, 1,400 / 20 = 70, 1,400 / 350 = 4.
    # EWR lyft: 2,500 / 25 = 100, 2,000 / 25 = 80, 2,000 / 500 = 4.
    expected = [
        ("EWR", "lyft", 25, 100.0, 80.0, 4.0),
        ("JFK", "uber", 50, 80.0, 60.0, 3_000 / 900),
        ("JFK", "yellow", 20, 80.0, 70.0, 4.0),
    ]
    assert table.to_pylist() == [pytest.approx(dict(zip(table.column_names, row))) for row in expected]
