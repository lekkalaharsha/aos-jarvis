from aos.config.loader import ensure_config, load_config


def test_ensure_config_creates_default(tmp_path):
    config_path = tmp_path / "config.toml"
    assert not config_path.exists()

    ensure_config(config_path)
    assert config_path.exists()


def test_load_config_returns_dict(tmp_path):
    config_path = tmp_path / "config.toml"
    config = load_config(config_path)
    assert config["project"]["phase"] == "phase0"
