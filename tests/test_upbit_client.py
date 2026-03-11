from investment_bot.services.upbit_client import UpbitClient


def test_upbit_client_reports_configuration_presence():
    client = UpbitClient(access_key="a", secret_key="b")
    assert client.configured() is True


def test_upbit_client_generates_jwt_like_token():
    client = UpbitClient(access_key="a", secret_key="b")
    token = client._create_jwt({"market": "KRW-BTC"})
    assert token.count(".") == 2
