from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import asyncio
from playwright.async_api import async_playwright
import json
import uuid

app = Flask(__name__)
CORS(app)

class WebsiteCapture:
    async def capture_sections(self, url, folder_name):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            try:
                # Create folder
                os.makedirs(f"captures/{folder_name}", exist_ok=True)
                
                # Go to page
                await page.goto(url, wait_until="networkidle", timeout=60000)
                
                # Capture sections
                results = {}
                for section in ["header", "hero", "footer"]:
                    element = await self._find_section(page, section)
                    if element:
                        # Save screenshot
                        screenshot_path = f"captures/{folder_name}/{section}.png"
                        await element.screenshot(path=screenshot_path)
                        
                        # Extract text
                        text = await element.inner_text()
                        text = ' '.join(text.split()).strip()[:500]
                        
                        results[section] = {
                            "screenshot": screenshot_path,
                            "text": text
                        }
                
                # Save JSON
                with open(f"captures/{folder_name}/data.json", "w") as f:
                    json.dump(results, f)
                
                return {"status": "success", "folder": folder_name}
            
            except Exception as e:
                return {"status": "error", "message": str(e)}
            finally:
                await browser.close()

    async def _find_section(self, page, section_type):
        selectors = {
    "header": [
        "header",
        "[role='banner']",
        ".header",
        "#header",
        ".site-header",
        ".page-header",
        ".main-header",
        ".top-header",
        "nav",
        ".navbar",
        ".nav-bar"
    ],
    "hero": [
        ".hero",
        ".banner",
        ".jumbotron",
        "#hero",
        "#banner",
        ".hero-section",
        ".main-banner",
        ".intro",
        ".landing-hero",
        ".top-section",
        ".hero-container",
        ".cover",
        ".splash"
    ],
    "footer": [
        "footer",
        "[role='contentinfo']",
        ".footer",
        "#footer",
        ".site-footer",
        ".page-footer",
        ".main-footer",
        ".bottom-footer",
        ".footer-container"
    ]
}

        
        for selector in selectors[section_type]:
            element = await page.query_selector(selector)
            if element and await element.is_visible():
                return element
        return None

def run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

@app.route('/capture', methods=['POST'])
def capture():
    data = request.get_json()
    urls = data.get('urls', [])
    
    if len(urls) != 3:
        return jsonify({"error": "Exactly 3 URLs required"}), 400
    
    # Create folders for each site
    folders = [f"site_{i+1}" for i in range(3)]
    
    # Capture all sites
    capturer = WebsiteCapture()
    results = []
    for url, folder in zip(urls, folders):
        result = run_async(capturer.capture_sections(url, folder))
        results.append({
            "url": url,
            "folder": folder,
            "status": result.get("status", "error"),
            "message": result.get("message", "")
        })
    
    return jsonify({"results": results})

if __name__ == '__main__':
    os.makedirs("captures", exist_ok=True)
    app.run(host='0.0.0.0', port=5000)