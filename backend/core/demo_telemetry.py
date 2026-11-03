"""Static demo fixtures: the only telemetry values permitted to leave for Gemini."""
FIXTURES = {
    "Company A (Demo)": ("LC-A-01", "Bangkok", [
        ("192.0.2.10", "a-web-01", "WEB_SERVER", "SUSPICIOUS_LOGIN", "Multiple failed login attempts"),
        ("192.0.2.20", "a-db-01", "DATABASE", "ACCESS_DENIED", "Database login denied"),
    ]),
    "Company B (Demo)": ("LC-B-01", "Chiang Mai", [
        ("198.51.100.10", "b-web-01", "WEB_SERVER", "PORT_SCAN", "Unusual connection attempts"),
        ("198.51.100.20", "b-fw-01", "FIREWALL", "BLOCKED_TRAFFIC", "Firewall blocked suspicious traffic"),
    ]),
}
