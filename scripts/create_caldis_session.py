"""
Standalone helper to create/refresh the caldis.pl session file.

Opens a visible Chromium window so you can log in manually.
Saves storage state to assets/temp/caldis_session.json and exits.

Usage:
    python scripts/create_caldis_session.py

Requirements:
    pip install playwright
    python -m playwright install chromium
"""
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SESSION_FILE = PROJECT_ROOT / "assets" / "temp" / "caldis_session.json"


async def main():
    from playwright.async_api import async_playwright

    print("Otwieranie przegladarki Chromium...")
    print(f"Plik sesji bedzie zapisany: {SESSION_FILE}")
    print()
    print("INSTRUKCJA:")
    print("  1. Zaloguj sie recznie w oknie przegladarki")
    print("  2. Po zalogowaniu skrypt zapisze sesje i zakonczy dzialanie")
    print("  3. Masz 3 minuty na zalogowanie")
    print()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        ctx = await browser.new_context(accept_downloads=False)
        page = await ctx.new_page()

        await page.goto("https://caldis.pl/logowanie", wait_until="networkidle")
        print("Przegladarka otwarta — zaloguj sie teraz...")

        try:
            await page.wait_for_url(
                lambda url: "logowanie" not in url.lower(),
                timeout=180_000,
            )
        except Exception:
            print("BLAD: Timeout — nie zalogowano sie w ciagu 3 minut.")
            await browser.close()
            sys.exit(1)

        print("Zalogowano pomyslnie! Zapisuje sesje...")
        SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        await ctx.storage_state(path=str(SESSION_FILE))
        print(f"Sesja zapisana: {SESSION_FILE}")
        await browser.close()

    print()
    print("Gotowe! Mozesz teraz uruchomic import z poziomu aplikacji.")


if __name__ == "__main__":
    asyncio.run(main())
