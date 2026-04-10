import asyncio
from playwright.async_api import async_playwright
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException
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
    """
    async with async_playwright() as p:
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
            # Navigate to the MPHC cause list page
            await page.goto(
                "https://mphc.gov.in/causelist",
                wait_until="domcontentloaded",
                timeout=60000,
            )

            stage = "Waiting for and clicking Lawyer tab"
            lawyer_tab = page.locator("a:has-text('Lawyer'), text=Lawyer").first
            await lawyer_tab.wait_for(state="visible", timeout=15000)
            await lawyer_tab.click(force=True)

            stage = "Waiting for and filling enrollment number"
            # Target the specific ID or placeholder
            enroll_input = page.locator("#lname, input[placeholder*='Lawyer Name'], input[placeholder*='Enrollment']").first
            await enroll_input.wait_for(state="visible", timeout=15000)
            await enroll_input.fill(f"{enroll_no}/{enroll_year}", force=True)

            stage = "Waiting for and filling date"
            # Target the datepicker class directly
            date_input = page.locator("input.datepicker:visible, input[name*='date']:visible").first
            # Small wait just to ensure UI is ready
            await page.wait_for_timeout(1000)
            await date_input.fill(target_date, force=True)

            stage = "Clicking SHOW button"
            show_btn = page.locator("button:has-text('SHOW'), input[type='button'][value='SHOW'], input[type='submit'][value='SHOW']").first
            await show_btn.wait_for(state="visible", timeout=15000)
            await show_btn.click(force=True)

            stage = "Waiting for results to load"
            # Wait for network idle or a specific timeout
            try:
                await page.wait_for_load_state("networkidle", timeout=15000)
            except:
                pass
            await page.wait_for_timeout(3000)

            stage = "Extracting page content"
            content = await page.content()

            # Check if results contain the enrollment number
            enrollment_str = f"{enroll_no}/{enroll_year}"
            if enrollment_str in content:
                stage = "Extracting results table"
                # Try to extract the results table
                results_text = await page.inner_text("body")

                return {
                    "status": "success",
                    "found": True,
                    "date": target_date,
                    "enrollment": enrollment_str,
                    "data": results_text,
                    "extracted_at": datetime.now().isoformat(),
                }
            else:
                return {
                    "status": "success",
                    "found": False,
                    "date": target_date,
                    "enrollment": enrollment_str,
                    "message": "No records found for this date",
                    "extracted_at": datetime.now().isoformat(),
                }

        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed at stage: '{stage}'. Error: {str(e)}",
                "date": target_date,
                "enrollment": f"{enroll_no}/{enroll_year}",
                "extracted_at": datetime.now().isoformat(),
            }
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

    Parameters:
    - no: Enrollment number (default: 724)
    - year: Enrollment year (default: 1984)
    - date: Target date in DD-MM-YYYY format (default: tomorrow)
    """
    if not date:
        # Default to tomorrow's date
        tomorrow = datetime.now() + timedelta(days=1)
        date = tomorrow.strftime("%d-%m-%Y")

    result = await run_scraper(no, year, date)

    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])

    return result


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
