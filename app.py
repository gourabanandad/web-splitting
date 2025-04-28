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
            page = await browser.new_page(viewport={'width': 1280, 'height': 720})
            
            try:
                os.makedirs(f"captures/{folder_name}", exist_ok=True)
                
                # Load the page with multiple strategies
                await self._load_page_with_retries(page, url)
                
                results = {}
                
                # Capture header
                header = await self._capture_section(page, "header", folder_name)
                if header:
                    results["header"] = header
                
                # Capture hero with improved detection
                hero = await self._capture_hero_section(page, folder_name)
                if hero:
                    results["hero"] = hero
                
                # Capture footer
                footer = await self._capture_section(page, "footer", folder_name)
                if footer:
                    results["footer"] = footer
                
                # Save results
                with open(f"captures/{folder_name}/data.json", "w") as f:
                    json.dump(results, f)
                
                return {"status": "success", "folder": folder_name}
            
            except Exception as e:
                return {"status": "error", "message": str(e)}
            finally:
                await browser.close()

    async def _load_page_with_retries(self, page, url):
        """Try multiple loading strategies"""
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
        except:
            try:
                await page.goto(url, wait_until="load", timeout=30000)
            except:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)

    async def _capture_section(self, page, section_type, folder_name):
        """Generic section capture"""
        selectors = {
            "header": ["header", "[role='banner']", ".header", "#header"],
            "footer": ["footer", "[role='contentinfo']", ".footer", "#footer"]
        }
        
        for selector in selectors[section_type]:
            element = await page.query_selector(selector)
            if element and await element.is_visible():
                box = await element.bounding_box()
                if box and box['width'] > 100 and box['height'] > 50:
                    path = f"captures/{folder_name}/{section_type}.png"
                    await element.screenshot(path=path)
                    return {
                        "screenshot": path,
                        "text": await self._clean_text(element)
                    }
        return None

    async def _capture_hero_section(self, page, folder_name):
        """Specialized hero section detection"""
        # Try common hero selectors first
        hero_selectors = [
            ".hero", ".banner", ".jumbotron", 
            ".hero-section", ".hero-banner",
            "section:first-of-type", "main > div:first-child",
            "[data-section='hero']", "[data-component='hero']"
        ]
        
        for selector in hero_selectors:
            element = await page.query_selector(selector)
            if element and await element.is_visible():
                box = await element.bounding_box()
                if box and box['width'] > 300 and box['height'] > 200:
                    path = f"captures/{folder_name}/hero.png"
                    await element.screenshot(path=path)
                    return {
                        "screenshot": path,
                        "text": await self._clean_text(element)
                    }
        
        # Fallback: Find largest section at top of page
        sections = await page.query_selector_all("section, div, header")
        hero_candidate = None
        max_area = 0
        
        for section in sections:
            if await section.is_visible():
                box = await section.bounding_box()
                if box:
                    area = box['width'] * box['height']
                    # Prioritize sections near top of page
                    if box['y'] < 500 and area > max_area and area > 100000:
                        max_area = area
                        hero_candidate = section
        
        if hero_candidate:
            path = f"captures/{folder_name}/hero.png"
            await hero_candidate.screenshot(path=path)
            return {
                "screenshot": path,
                "text": await self._clean_text(hero_candidate)
            }
        
        return None

    async def _clean_text(self, element):
        """Clean extracted text"""
        text = await element.inner_text()
        return ' '.join(text.split()).strip()[:500]

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
    
    folders = [f"site_{i+1}" for i in range(3)]
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