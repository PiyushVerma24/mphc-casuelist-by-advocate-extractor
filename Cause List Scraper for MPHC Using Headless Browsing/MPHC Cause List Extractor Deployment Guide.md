# MPHC Cause List Extractor Deployment Guide

This guide provides steps to deploy your cause list extractor on **Railway** and integrate it with **Vercel Cron Jobs**.

## 1. Deploying to Railway

Railway is ideal for this because it handles Docker and Playwright seamlessly.

### Steps:
1.  **Create a New Project**: Log in to [Railway.app](https://railway.app/) and click **"New Project"**.
2.  **Upload Code**: Choose **"Deploy from GitHub repo"** (you can push the files I've created to a private repo).
3.  **Automatic Build**: Railway will detect the `Dockerfile` and build the container automatically.
4.  **Environment Variables**:
    *   `PORT`: Set to `8000` (Railway often sets this automatically).
5.  **Networking**: Go to the **Settings** tab and click **"Generate Domain"** to get a public URL (e.g., `https://mphc-extractor-production.up.railway.app`).

## 2. Storing Results

The current script returns a **JSON response** with the cause list details. 

### How to store results:
*   **Database**: You can modify `app.py` to save the results to a database (like Supabase or MongoDB).
*   **Webhook**: You can have the script send a POST request to another service (like Slack or an email API) whenever a case is found.
*   **Log Storage**: Railway keeps logs of all successful runs, which you can view in their dashboard.

## 3. Integrating with Vercel Cron Jobs

You can use **Vercel** to trigger the extraction every day at a specific time.

### Steps:
1.  **Create a `vercel.json`** in your Vercel project:
    ```json
    {
      "crons": [
        {
          "path": "/api/trigger-extraction",
          "schedule": "0 18 * * *"
        }
      ]
    }
    ```
2.  **Create the API Route** in Vercel (`/api/trigger-extraction.js`):
    ```javascript
    export default async function handler(req, res) {
      const railwayUrl = "https://your-railway-url.up.railway.app/extract?no=724&year=1984";
      const response = await fetch(railwayUrl);
      const data = await response.json();
      
      // Handle the data (e.g., send an email if a case is found)
      if (data.found) {
        console.log("Case found for tomorrow!");
      }
      
      res.status(200).json({ success: true, data });
    }
    ```

This setup ensures that **Vercel** acts as the "scheduler" (Cron), while **Railway** does the heavy lifting of browsing the MPHC website.
