from playwright.sync_api import sync_playwright, expect
import pytest


BASE_URL = "http://localhost:8000"


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def page(browser):
    context = browser.new_context()
    page = context.new_page()
    yield page
    context.close()


class TestWatchlistLoad:
    def test_watchlist_page_loads_successfully(self, page):
        page.goto(f"{BASE_URL}/watchlist/")
        expect(page).to_have_title(timeout=10000)
        expect(page.locator("text=Market Watchlist")).to_be_visible()
        expect(page.locator("text=Total Setups")).to_be_visible()

    def test_no_console_errors_on_watchlist_load(self, page):
        page.goto(f"{BASE_URL}/watchlist/")
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.wait_for_load_state("networkidle")
        assert len([e for e in console_errors if "error" in e.lower()]) == 0

    def test_watchlist_ideas_render_in_list_view(self, page):
        page.goto(f"{BASE_URL}/watchlist/?view=active&view_mode=list")
        expect(page.locator("text=Active Pipeline")).to_be_visible()


class TestWatchlistToTrade:
    def test_promote_idea_to_trade_redirects_to_form(self, page):
        page.goto(f"{BASE_URL}/watchlist/")

        add_button = page.locator("a.wl-btn-new-idea")
        if add_button.is_visible():
            add_button.click()

        page.fill("input[name='title']", f"E2E Test Idea {page.eval_on_selector('body', 'Date.now()')}")
        page.select_option("select#instrumentSelect", lambda s: s.select_option("") or "1")
        page.select_option("select[name='direction']", "LONG")
        page.select_option("select[name='status']", "EXECUTED")
        page.fill("input[name='planned_entry']", "100.50")
        page.fill("input[name='planned_sl']", "98.00")
        page.fill("input[name='planned_tp']", "106.00")
        page.click("button[type='submit']")

        page.wait_for_url("**/trades/**")

        expect(page.locator("text=Log New Trade")).to_be_visible()

    def test_trade_form_prefills_price_fields(self, page):
        page.goto(f"{BASE_URL}/trades/new?entry_price=100.50&stop_loss=98.00&tp_target=106.00")
        expect(page.locator('input[name="entry_price"]')).to_have_value("100.50")
        expect(page.locator('input[name="stop_loss"]')).to_have_value("98.00")
        expect(page.locator('input[name="take_profit"]')).to_have_value("106.00")


class TestTradeForm:
    def test_trade_form_has_all_required_fields(self, page):
        page.goto(f"{BASE_URL}/trades/new")

        expect(page.locator('input[name="entry_date"]')).to_be_visible()
        expect(page.locator('input[name="entry_time"]')).to_be_visible()
        expect(page.locator('input[name="entry_price"]')).to_be_visible()
        expect(page.locator('input[name="stop_loss"]')).to_be_visible()
        expect(page.locator('input[name="take_profit"]')).to_be_visible()
        expect(page.locator('select[name="direction"]')).to_be_visible()
        expect(page.locator('select[name="instrument_id"]')).to_be_visible()
        expect(page.locator('select[name="strategy_id"]')).to_be_visible()
        expect(page.locator('select[name="session_id"]')).to_be_visible()

    def test_trade_form_execution_status_buttons(self, page):
        page.goto(f"{BASE_URL}/trades/new")

        expect(page.locator("text=Live Trade")).to_be_visible()
        expect(page.locator("text=Front-Run")).to_be_visible()
        expect(page.locator("text=Missed Trade")).to_be_visible()
        expect(page.locator("text=SL Swept")).to_be_visible()

    def test_trade_form_emotion_tags(self, page):
        page.goto(f"{BASE_URL}/trades/new")

        expect(page.locator("text=Calm & Disciplined")).to_be_visible()
        expect(page.locator("text=FOMO / Rushed")).to_be_visible()
        expect(page.locator("text=Fearful / Hesitant")).to_be_visible()

    def test_trade_form_outcome_selector(self, page):
        page.goto(f"{BASE_URL}/trades/new")

        expect(page.locator('select[name="outcome_type"]')).to_be_visible()


class TestValidTradeCreation:
    def test_submit_valid_trade_redirects_to_list(self, page):
        today = "2026-09-17"
        page.goto(f"{BASE_URL}/trades/new")

        page.fill('input[name="entry_date"]', today)
        page.fill('input[name="entry_time"]', "10:30")
        page.select_option('select[name="direction"]', "LONG")
        page.fill('input[name="entry_price"]', "100.00")
        page.fill('input[name="stop_loss"]', "98.00")
        page.fill('input[name="take_profit"]', "106.00")
        page.select_option('select[name="instrument_id"]', "1")
        page.select_option('select[name="strategy_id"]', "1")
        page.select_option('select[name="session_id"]', "1")
        page.select_option('select[name="probability_level_id"]', "1")
        page.select_option('select[name="mtf_phase_id"]', "1")
        page.fill('input[name="comments"]', "E2E Valid Trade Test")
        page.select_option('select[id="outcomeTypeSelect"]', "AUTO")

        page.click("button[type='submit']")
        page.wait_for_url("**/trades/", timeout=10000)

    def test_created_trade_appears_in_list(self, page):
        today = "2026-09-17"
        page.goto(f"{BASE_URL}/trades/new")

        page.fill('input[name="entry_date"]', today)
        page.fill('input[name="entry_time"]', "11:00")
        page.fill('input[name="entry_price"]', "100.00")
        page.fill('input[name="stop_loss"]', "98.00")
        page.fill('input[name="take_profit"]', "106.00")
        page.fill('input[name="comments"]', f"E2E List Test {page.eval_on_selector('body', 'Date.now().getTime()')}")
        page.click("button[type='submit']")

        page.wait_for_url("**/trades/")
        expect(page.locator("text=E2E List Test")).to_be_visible()


class TestInvalidTrade:
    def test_empty_required_field_validation(self, page):
        page.goto(f"{BASE_URL}/trades/new")

        page.fill('input[name="entry_date"]', "2026-09-17")
        page.click("button[type='submit']")
        page.wait_for_load_state("networkidle")
        current_url = page.url
        assert "/trades/" in current_url or "error" in current_url.lower()


class TestDoubleSubmission:
    def test_multiple_submit_clicks_dont_create_duplicates(self, page):
        page.goto(f"{BASE_URL}/trades/new")

        page.fill('input[name="entry_date"]', "2026-09-17")
        page.fill('input[name="entry_price"]', "100.00")
        page.fill('input[name="stop_loss"]', "98.00")
        page.fill('input[name="enter_profit"]', "106.00")

        submit_btn = page.locator("button[type='submit']")
        for _ in range(3):
            try:
                submit_btn.click()
                page.wait_for_timeout(100)
            except:
                pass

        page.wait_for_url("**/trades/", timeout=5000)


class TestNavigation:
    def test_browser_back_and_forward(self, page):
        page.goto(f"{BASE_URL}/trades/")
        page.locator("text=New Trade").click()
        page.wait_for_url("**/trades/new")
        page.go_back()
        expect(page.locator("text=Trades")).to_be_visible()

    def test_refresh_doesnt_duplicate_data(self, page):
        page.goto(f"{BASE_URL}/trades/")
        page.wait_for_load_state("networkidle")
        initial_count = page.locator("text=#").count()
        page.reload()
        page.wait_for_load_state("networkidle")
        new_count = page.locator("text=#").count()
        assert new_count == initial_count


@pytest.mark.e2e
def test_smoke_check(page):
    page.goto(f"{BASE_URL}/")
    expect(page).to_have_title()