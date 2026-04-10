import asyncio
from playwright.async_api import async_playwright
from datetime import datetime, timedelta
import pandas as pd
import sys

async def extract_cause_list(enroll_no, enroll_year, target_date=None):
    if target_date is None:
        # Default to next day
        target_date = (datetime.now() + timedelta(days=1)).strftime("%d-%m-%p")
    
    # Standardizing the enrollment number format as per site instructions
    # Site says: if Enroll. No. is MP/123-A/2017 then type 123-A2017
    # For 724/1984, it should likely be 724-1984 or just 724/1984
    # Based on the screenshot, 724/1984 was typed directly.
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            print(f"Navigating to MPHC Causelist for {enroll_no}/{enroll_year} on {target_date}...")
            await page.goto("https://mphc.gov.in/causelist", wait_until="networkidle", timeout=60000)
            
            # Click the Lawyer tab
            # The screenshot shows it's a tab interface
            lawyer_tab = await page.get_by_text("Lawyer", exact=True)
            await lawyer_tab.click()
            
            # Fill Enrollment Number
            # We'll look for the input field near the instruction text
            enroll_input = await page.locator("input[type='text']").first # Usually the first text box in that tab
            await enroll_input.fill(f"{enroll_no}/{enroll_year}")
            
            # Set Date
            # The date input usually has a specific format or id
            date_input = await page.locator("input[name*='date'], #date, .datepicker").first
            await date_input.fill(target_date)
            
            # Click Show
            await page.get_by_role("button", name="SHOW").click()
            
            # Wait for results
            await page.wait_for_timeout(5000) # Wait for AJAX/DOM update
            
            # Extract table data
            # This part would be refined based on the actual DOM structure
            # For now, we'll look for tables containing the enrollment number
            content = await page.content()
            
            if f"{enroll_no}/{enroll_year}" in content:
                print("Success: Found cause list entries.")
                # Logic to parse the specific table rows shown in screenshot
                # We'll save the screenshot for verification in automated runs
                await page.screenshot(path=f"causelist_{target_date.replace('-', '_')}.png")
                return True
            else:
                print("No records found for the given criteria.")
                return False
                
        except Exception as e:
            print(f"Error during extraction: {e}")
            return False
        finally:
            await browser.close()

if __name__ == "__main__":
    # Usage: python3 mphc_extractor.py 724 1984 [DD-MM-YYYY]
    e_no = sys.argv[1] if len(sys.argv) > 1 else "724"
    e_year = sys.argv[2] if len(sys.argv) > 2 else "1984"
    t_date = sys.argv[3] if len(sys.argv) > 3 else None
    
    asyncio.run(extract_cause_list(e_no, e_year, t_date))
