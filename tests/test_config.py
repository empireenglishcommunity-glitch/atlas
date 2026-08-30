from src.atlas import config as cfg


def test_load_settings_reads_env_and_types():
    s = cfg.load_settings({
        "TELEGRAM_BOT_TOKEN": "tok",
        "OWNER_CHAT_ID": "12345",
        "GROQ_API_KEY": "gk",
        "BRIEF_HOUR": "6",
        "TIMEZONE": "Africa/Cairo",
    })
    assert s.telegram_bot_token == "tok"
    assert s.owner_chat_id == 12345
    assert s.brief_hour == 6
    assert s.timezone == "Africa/Cairo"
    # tz + now are wired
    assert s.now().tzinfo is not None


def test_defaults_when_env_missing():
    s = cfg.load_settings({})
    assert s.owner_chat_id == 0
    assert s.groq_model == "openai/gpt-oss-120b"
    assert s.kokoro_voice == "af_heart"
    assert s.chronotype == "morning"
    assert s.brief_hour == 6


def test_bad_int_falls_back_to_default():
    s = cfg.load_settings({"BRIEF_HOUR": "not-a-number", "OWNER_CHAT_ID": ""})
    assert s.brief_hour == 6
    assert s.owner_chat_id == 0


def test_neglect_thresholds_by_kind():
    # health slides fastest, so it is watched tightest (R6.3)
    assert cfg.neglect_days_for("health") == 3
    assert cfg.neglect_days_for("work") == 7
    assert cfg.neglect_days_for("personal") == 5
    assert cfg.neglect_days_for("unknown") == 7  # safe default


def test_seed_domains_include_health_and_work():
    names = {d["name"] for d in cfg.SEED_DOMAINS}
    assert {"gym", "diet", "deen"} <= names          # health, the owner's fragile ones
    assert {"empire", "trading", "relationships"} <= names
    assert "real_estate" not in names                # removed per owner
