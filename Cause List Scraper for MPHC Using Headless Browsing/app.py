import asyncio
from playwright.async_api import async_playwright
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException
from typing import Optional
import os

app = FastAPI()

async def run_scraper(enroll_no: str, enroll_year: str, target_date: str):
    async with async_playwright() as p:
        # Standard Playwright launch for Docker
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        page = await browser.new_page()
        
        try:
            print(f"Navigating to MPHC for {enroll_no}/{enroll_year} on {target_date}")
            # Increased timeout and added more robust navigation
            await page.goto("https://mphc.gov.in/causelist", wait_until="domcontentloaded", timeout=60000)
            
            # Click Lawyer tab - using more resilient selectors
            await page.click("text=Lawyer")
            
            # Fill enrollment
            # Based on the site structure, finding the first visible text input in the active tab
            await page.fill("input[type='text']:visible", f"{enroll_no}/{enroll_year}")
            
            # Fill date
            # Target the date input specifically
            await page.fill("input[name*='date']:visible", target_date)
            
            # Click SHOW
            await page.click("button:has-text('SHOW')")
            
            # Wait for results to load
            await page.wait_for_timeout(5000)
            
            # Extract data
            content = await page.content()
            
            # Basic extraction logic - returns the full text of the results area
            # In a production environment, you'd parse this into a clean JSON structure
            if f"{enroll_no}/{enroll_year}" in content:
                # Find the result container (usually a table or div)
                results = await page.inner_text("body") # Simplified for now
                return {
                    "status": "success",
                    "found": True,
                    "date": target_date,
                    "enrollment": f"{enroll_no}/{enroll_year}",
                    "data": results
                }
            else:
                return {
                    "status": "success",
                    "found": False,
                    "date": target_date,
                    "enrollment": f"{enroll_no}/{enroll_year}",
                    "message": "No records found"
                }
                
        except Exception as e:
            print(f"Scraper error: {e}")
            return {"status": "error", "message": str(e)}
        finally:
            await browser.close()

@app.get("/extract")
async def extract(no: str = "724", year: str = "1984", date: Optional[str] = None):
    if not date:
        # Default to tomorrow
        date = (datetime.now() + timedelta(days=1)).strftime("%d-%m-%Y")
    
    result = await run_scraper(no, year, date)
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    return result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
