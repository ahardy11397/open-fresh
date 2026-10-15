from openfresh import db, settings


def test_settings_roundtrip(tmp_path):
    conn = db.get_conn(str(tmp_path / "kitchen.db"))
    db.init_db(conn)

    assert settings.get_setting(conn, "missing_key") is None
    assert settings.get_setting(conn, "missing_key", "fallback") == "fallback"

    settings.set_setting(conn, "theme", "dark")
    assert settings.get_setting(conn, "theme") == "dark"

    settings.set_setting(conn, "theme", "light")
    assert settings.get_setting(conn, "theme") == "light"


def test_get_household_size(tmp_path):
    conn = db.get_conn(str(tmp_path / "kitchen.db"))
    db.init_db(conn)

    assert settings.get_household_size(conn) == 2

    settings.set_setting(conn, "household_size", "5")
    assert settings.get_household_size(conn) == 5
