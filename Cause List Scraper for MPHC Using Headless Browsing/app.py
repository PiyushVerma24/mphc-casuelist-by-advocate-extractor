import asyncio
import json
from playwright.async_api import async_playwright
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional
import os

app = FastAPI(title="MPHC Cause List Extractor")


@app.get("/health")
async def health():
    """Health check endpoint for Railway."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/")
async def root():
    """Root endpoint with usage instructions."""
    return {
        "service": "MPHC Cause List Extractor",
        "version": "1.0.0",
        "usage": {
            "extract": "/extract?no=724&year=1984",
            "extract_with_date": "/extract?no=724&year=1984&date=10-04-2026",
            "health": "/health",
        },
        "note": "If no date is provided, it defaults to tomorrow's date.",
    }


async def run_scraper(enroll_no: str, enroll_year: str, target_date: str):
    """
    Scrape the MPHC cause list for a given advocate enrollment number.
    Uses the Lawyer tab on https://mphc.gov.in/causelist (no captcha required).
    Yields string updates so the browser can see progress in real time.
    """
    async def log_stage(msg: str):
        return f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n"

    yield await log_stage(f"Initializing scraper for {enroll_no}/{enroll_year} on {target_date}...")

    async with async_playwright() as p:
        yield await log_stage("Launching headless browser...")
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--single-process",
            ],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        page = await context.new_page()
        page.set_default_timeout(60000)

        stage = "Starting"
        try:
            stage = "Navigating to MPHC cause list page"
            yield await log_stage(stage)
            for attempt in range(3):
                try:
                    await page.goto(
                        "https://mphc.gov.in/causelist",
                        wait_until="domcontentloaded",
                        timeout=60000,
                    )
                    break
                except Exception as e:
                    if attempt == 2:
                        raise e
                    yield await log_stage(f"Network error, retrying navigation (attempt {attempt+2}/3)...")
                    await page.wait_for_timeout(3000)

            stage = "Waiting for and clicking Lawyer tab"
            yield await log_stage(stage)
            lawyer_tab = page.locator("text=Lawyer").first
            await lawyer_tab.wait_for(state="visible", timeout=15000)
            await lawyer_tab.click(force=True)

            stage = "Waiting for and filling enrollment number"
            yield await log_stage(stage)
            enroll_input = page.locator("#lname, input[placeholder*='Lawyer Name'], input[placeholder*='Enrollment']").first
            await enroll_input.wait_for(state="visible", timeout=15000)
            await enroll_input.fill(f"{enroll_no}/{enroll_year}", force=True)

            stage = "Waiting for and filling date"
            yield await log_stage(stage)
            date_input = page.locator("input.datepicker:visible, input[name*='date']:visible").first
            await page.wait_for_timeout(1000)
            await date_input.fill(target_date, force=True)
            # Dismiss the datepicker popup so it doesn't block UI
            await page.keyboard.press("Escape")

            stage = "Selecting 'MOTION' radio button"
            yield await log_stage(stage)
            try:
                # Based on user feedback, ensure the MOTION radio button is explicitly selected.
                motion_label = page.locator("label:has-text('MOTION'):visible, input[type='radio']:visible:near(label:has-text('MOTION'))").first
                await motion_label.click(force=True)
                # also explicitly force check via js just in case
                await page.evaluate("document.querySelectorAll('input[type=radio]').forEach(r => { if(r.nextElementSibling && r.nextElementSibling.innerText.includes('MOTION')) r.checked = true; })")
            except Exception as e:
                pass # Silently proceed if already selected or not found

            stage = "Clicking SHOW button"
            yield await log_stage(stage)
            # Use JS to invoke the click directly. This bypasses ANY issues with the 
            # datepicker overlay eating the click event in headless mode. 
            await page.evaluate("if(document.getElementById('bt12')) document.getElementById('bt12').click(); else get_lw();")

            stage = "Waiting for results to load"
            yield await log_stage(stage)
            
            # Hook the dialog listener to catch "No record found" or "Please select..." alerts
            alert_messages = []
            async def handle_dialog(dialog):
                alert_messages.append(dialog.message)
                yield await log_stage(f"Website threw alert: {dialog.message}")
                await dialog.accept()
            page.on("dialog", handle_dialog)
            
            has_data = False
            # Wait up to 45 seconds explicitly for the AJAX content container to populate
            for _ in range(45):
                if alert_messages:
                    break
                    
                try:
                    r_box_text = await page.locator("#r_box_lw").inner_text(timeout=500)
                    if r_box_text and len(r_box_text.strip()) > 5:
                        has_data = True
                        break
                except:
                    pass
                await page.wait_for_timeout(1000)

            stage = "Extracting page content"
            yield await log_stage(stage)
            
            if alert_messages:
                yield "\n--- Final Result ---\n"
                yield json.dumps({
                    "status": "success",
                    "found": False,
                    "date": target_date,
                    "enrollment": f"{enroll_no}/{enroll_year}",
                    "message": f"Website Alert: {alert_messages[0]}",
                    "extracted_at": datetime.now().isoformat(),
                }, indent=2) + "\n"
            elif has_data:
                stage = "Extracting results table"
                yield await log_stage(stage)
                try:
                    results_text = await page.inner_text("#r_box_lw")
                except:
                    results_text = await page.inner_text("body")

                yield "\n--- Final Result ---\n"
                yield json.dumps({
                    "status": "success",
                    "found": True,
                    "date": target_date,
                    "enrollment": f"{enroll_no}/{enroll_year}",
                    "data": results_text,
                    "extracted_at": datetime.now().isoformat(),
                }, indent=2) + "\n"
            else:
                yield "\n--- Final Result ---\n"
                yield json.dumps({
                    "status": "success",
                    "found": False,
                    "date": target_date,
                    "enrollment": f"{enroll_no}/{enroll_year}",
                    "message": "Timed out waiting for results. No data rendered and no alert was shown (Could be a slow network or no records).",
                    "extracted_at": datetime.now().isoformat(),
                }, indent=2) + "\n"

        except Exception as e:
            yield "\n--- Final Result ---\n"
            yield json.dumps({
                "status": "error",
                "message": f"Failed at stage: '{stage}'. Error: {str(e)}",
                "date": target_date,
                "enrollment": f"{enroll_no}/{enroll_year}",
                "extracted_at": datetime.now().isoformat(),
            }, indent=2) + "\n"
        finally:
            await context.close()
            await browser.close()


@app.get("/extract")
async def extract(
    no: str = "724",
    year: str = "1984",
    date: Optional[str] = None,
):
    """
    Extract cause list for a given advocate enrollment number.
    Now returning a StreamingResponse that yields progress lines in real time.
    """
    if not date:
        # Default to tomorrow's date
        tomorrow = datetime.now() + timedelta(days=1)
        date = tomorrow.strftime("%d-%m-%Y")

    # Return a streaming response so the browser sees updates live
    return StreamingResponse(
        run_scraper(no, year, date),
        media_type="text/plain"
    )


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
