"""Take Amazon Appstore screenshots of JARVIS Android UI (phone size)."""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

OUT = Path("screenshots")
OUT.mkdir(exist_ok=True)
HTML = Path("C:/JARVISCore/ui/android.html").resolve().as_uri()

async def shot(page, name):
    path = str(OUT / f"{name}.png")
    await page.screenshot(path=path)
    print(f"  saved {name}.png")

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=2,
            user_agent="Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36",
        )
        page = await ctx.new_page()
        await page.goto(HTML, wait_until="domcontentloaded")
        await page.wait_for_timeout(600)

        # ── 1. Boot screen ────────────────────────────────────────────────────
        await shot(page, "01_boot")

        # ── 2. Setup screen ───────────────────────────────────────────────────
        await page.evaluate("""
            document.getElementById('bootloader').style.display = 'none';
            const ss = document.getElementById('setup-screen');
            ss.style.display = 'flex';
            ss.style.visibility = 'visible';
            ss.style.opacity = '1';
        """)
        await page.wait_for_timeout(500)
        await shot(page, "02_setup")

        # ── 3. Main app (chat tab) ─────────────────────────────────────────────
        await page.evaluate("""
            document.getElementById('bootloader').style.display = 'none';
            document.getElementById('setup-screen').style.display = 'none';
            const app = document.getElementById('app');
            app.style.display = 'flex';
            app.style.visibility = 'visible';
            app.style.opacity = '1';
            // Make sure chat tab is visible
            const chatTab = document.getElementById('tab-chat');
            if(chatTab){ chatTab.style.display='flex'; chatTab.classList.add('active'); }
            // Set plan label
            const planEl = document.querySelector('.plan-badge, #plan-label, .plan-lbl');
            if(planEl) planEl.textContent = 'PRO';
        """)
        await page.wait_for_timeout(500)
        await shot(page, "03_main_app")

        # ── 4. Scroll to show more of the chat tab ────────────────────────────
        await page.mouse.wheel(0, 300)
        await page.wait_for_timeout(300)
        await shot(page, "04_chat_actions")

        # ── 5. Settings tab ───────────────────────────────────────────────────
        await page.evaluate("""
            // Hide all tabs, show settings
            document.querySelectorAll('.tab').forEach(t => t.style.display='none');
            const settingsTab = document.getElementById('tab-settings') || document.querySelector('.tab-settings');
            if(settingsTab){ settingsTab.style.display='flex'; settingsTab.classList.add('active'); }
        """)
        await page.wait_for_timeout(500)
        await shot(page, "05_settings")

        await browser.close()
    print(f"\nDone — screenshots in ./{OUT}/")

asyncio.run(main())
