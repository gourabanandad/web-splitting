import asyncio
from playwright.async_api import async_playwright
import json
import os
from datetime import datetime
from typing import Dict, Optional
from flask import Flask, request, jsonify
import uuid
import threading

app = Flask(__name__)

class WebsiteSectionDetector:
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.timeout = 90000  # 90 seconds timeout
        self.section_selectors = {
            'header': [
                'header', 
                '[role="banner"]', 
                '.header',
                '#header',
                'div[class*="header"]'
            ],
            'hero': [
                '.hero',
                '.banner',
                '#hero',
                '.jumbotron',
                'section:first-of-type',
                'div[class*="hero"]'
            ],
            'footer': [
                'footer',
                '[role="contentinfo"]',
                '.footer',
                '#footer',
                'div[class*="footer"]'
            ],
            'text': [
                'article',
                'main',
                '.content',
                '.text-container',
                'section'
            ],
            'lists': [
                'ul',
                'ol',
                '.list',
                '.items'
            ]
        }

    async def detect_sections(self, url: str) -> Dict:
        """Detect sections and store screenshots in website-specific folder"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            )
            page = await context.new_page()
            
            try:
                # Create unique folder for this analysis
                analysis_id = str(uuid.uuid4())
                os.makedirs(f"output/{analysis_id}", exist_ok=True)
                
                # Load page with fallback strategies
                await self._load_page_with_fallback(page, url)
                
                # Scroll to trigger lazy loading
                await self._scroll_page(page)
                
                # Take full page screenshot
                full_page_path = f"output/{analysis_id}/full_page.png"
                await page.screenshot(path=full_page_path, full_page=True)
                
                results = {
                    'analysis_id': analysis_id,
                    'url': url,
                    'timestamp': datetime.now().isoformat(),
                    'sections': {},
                    'screenshots': {
                        'full_page': full_page_path
                    }
                }
                
                # Process each section type
                for section_name, selectors in self.section_selectors.items():
                    section_data = await self._process_section(page, section_name, analysis_id)
                    if section_data:
                        results['sections'][section_name] = section_data
                        results['screenshots'][section_name] = section_data['screenshot']
                
                # Save JSON results
                with open(f"output/{analysis_id}/results.json", 'w') as f:
                    json.dump(results, f, indent=2)
                
                return results
                
            except Exception as e:
                print(f"Error during detection: {str(e)}")
                return {'error': str(e)}
            finally:
                await context.close()
                await browser.close()

    async def _process_section(self, page, section_name: str, analysis_id: str) -> Optional[Dict]:
        """Detect and process a single section"""
        for selector in self.section_selectors[section_name]:
            try:
                element = await page.query_selector(selector)
                if element and await element.is_visible():
                    box = await element.bounding_box()
                    if not box or (box['width'] * box['height']) < 5000:
                        continue
                    
                    # Save screenshot
                    screenshot_path = f"output/{analysis_id}/{section_name}.png"
                    await element.screenshot(path=screenshot_path)
                    
                    # Extract and clean text
                    text = await element.inner_text()
                    cleaned_text = ' '.join(text.split()).strip()[:1000]
                    
                    return {
                        'screenshot': screenshot_path,
                        'text': cleaned_text,
                        'position': {
                            'x': box['x'],
                            'y': box['y'],
                            'width': box['width'],
                            'height': box['height']
                        },
                        'selector': selector
                    }
            except:
                continue
        return None

    # ... (keep other helper methods from your original class) ...

def run_async_in_thread(coroutine):
    """Helper to run async code in a thread"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(coroutine)

@app.route('/analyze', methods=['POST'])
def analyze_websites():
    """Endpoint to analyze multiple websites"""
    try:
        data = request.get_json()
        urls = data.get('urls', [])
        
        if len(urls) != 3:
            return jsonify({
                'status': 'error',
                'message': 'Exactly 3 URLs are required'
            }), 400
        
        detector = WebsiteSectionDetector(headless=True)
        all_results = []
        
        # Process each URL
        for url in urls:
            try:
                # Run the async detection in a thread
                result = run_async_in_thread(detector.detect_sections(url))
                if 'error' in result:
                    print(f"Error processing {url}: {result['error']}")
                    continue
                
                all_results.append({
                    'url': url,
                    'analysis_id': result['analysis_id'],
                    'screenshots': result['screenshots'],
                    'sections_found': list(result['sections'].keys())
                })
                
            except Exception as e:
                print(f"Failed to process {url}: {str(e)}")
                continue
        
        if not all_results:
            return jsonify({
                'status': 'error',
                'message': 'Failed to process all URLs'
            }), 500
        
        # Prepare response for the AI model
        response = {
            'status': 'success',
            'results': all_results,
            'next_steps': {
                'ai_processing': {
                    'json_files': [f"output/{res['analysis_id']}/results.json" for res in all_results],
                    'screenshot_folders': [f"output/{res['analysis_id']}" for res in all_results]
                }
            }
        }
        
        return jsonify(response)
    
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/status/<analysis_id>', methods=['GET'])
def check_status(analysis_id):
    """Check status of a specific analysis"""
    if os.path.exists(f"output/{analysis_id}/results.json"):
        return jsonify({'status': 'complete'})
    return jsonify({'status': 'processing'})

if __name__ == '__main__':
    # Create output directory if it doesn't exist
    os.makedirs("output", exist_ok=True)
    app.run(host='0.0.0.0', port=5000)