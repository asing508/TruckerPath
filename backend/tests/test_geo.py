from app.geo import Polyline, haversine_miles


def test_haversine_known_distance():
    # Dallas -> Houston is ~225 miles great-circle
    d = haversine_miles(32.7767, -96.7970, 29.7604, -95.3698)
    assert 215 < d < 240


def test_point_at_walks_the_line():
    line = Polyline.from_points([(30.0, -97.0), (30.0, -96.0), (31.0, -96.0)])
    lat, lon, _ = line.point_at(0.0)
    assert (round(lat, 3), round(lon, 3)) == (30.0, -97.0)
    lat, lon, _ = line.point_at(line.total_miles)
    assert (round(lat, 3), round(lon, 3)) == (31.0, -96.0)
    mid_lat, mid_lon, heading = line.point_at(line.cum_miles[1] / 2)
    assert abs(mid_lat - 30.0) < 1e-6 and -97.0 < mid_lon < -96.0
    assert 80 < heading < 100  # heading east


def test_distance_from_measures_lateral_offset():
    line = Polyline.from_points([(30.0, -97.0), (30.0, -96.0)])
    on_route = line.distance_from(30.0, -96.5)
    off_route = line.distance_from(30.05, -96.5)  # ~3.45 mi north
    assert on_route < 0.05
    assert 3.2 < off_route < 3.7


def test_distance_beyond_endpoints_projects_to_endpoint():
    line = Polyline.from_points([(30.0, -97.0), (30.0, -96.0)])
    d = line.distance_from(30.0, -95.5)  # past the east end
    # 0.5 deg lon x 69.05 mi/deg x cos(30 deg) ~= 29.9 mi
    assert 28 < d < 32
