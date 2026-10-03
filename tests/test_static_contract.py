from fastapi.testclient import TestClient


def test_public_page_and_local_assets_are_served(full_mock_stack):
    app, _, _, _ = full_mock_stack

    with TestClient(app) as client:
        page = client.get("/")
        stylesheet = client.get("/static/styles.css")
        script = client.get("/static/app.js")

    assert page.status_code == 200
    assert stylesheet.status_code == 200
    assert script.status_code == 200


def test_page_is_chinese_mobile_first_and_privacy_safe(full_mock_stack):
    app, _, _, _ = full_mock_stack

    with TestClient(app) as client:
        page = client.get("/")
        stylesheet = client.get("/static/styles.css")
        script = client.get("/static/app.js")

    html = page.text
    assert 'name="viewport"' in html
    assert "经营验证" in html
    assert "aria-live=" in html
    assert "虚构样例" in html
    assert "静态预览，未执行实时分析" in html
    assert 'href="/static/styles.css"' in html
    assert 'src="/static/app.js"' in html
    assert 'type="email"' not in html
    assert 'type="tel"' not in html
    assert "@media" in stylesheet.text
    assert "max-width" in stylesheet.text
    assert "textContent" in script.text
    assert "innerHTML" not in script.text
    assert all(value not in html + script.text for value in (
        "FEISHU_APP_SECRET", "DIFY_WORKFLOW_API_KEY", "DEEPSEEK_API_KEY"
    ))
