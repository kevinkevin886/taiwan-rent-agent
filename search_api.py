import asyncio
import random
import re
import requests
import os
import json
from playwright.async_api import async_playwright
from dotenv import load_dotenv

# 引入 Gemini API
import google.generativeai as genai

load_dotenv()
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
HISTORY_FILE = "history.json"

# 設定 Gemini API Key
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# ================= LLM 自然語言解析區 =================
def parse_natural_language(user_query: str) -> dict:
    """透過 LLM 將自然語言轉換為 591 爬蟲參數"""
    print(f"🧠 正在請求 LLM 解析你的需求：「{user_query}」...")
    
    prompt = f"""
    你是一個台灣租屋條件解析助理。請將使用者的自然語言租屋需求，轉換為嚴格的 JSON 格式。
    必須提取以下欄位，若使用者未提及某個條件，請將該欄位留空字串 "" 或空陣列 []：
    
    - TARGET_REGION: "1" (台北市) 或 "3" (新北市)。若未提及預設為 "1"。
    - SEARCH_KEYWORD: 地標、醫院、捷運站或路名 (例如 "台北榮總", "台大醫院")。
    - TARGET_MIN_PRICE: 最低租金數字 (純數字字串)。
    - TARGET_MAX_PRICE: 最高租金數字 (純數字字串，例如 5 萬請轉為 "50000")。
    - TARGET_MIN_AREA: 最小坪數數字 (純數字字串)。
    - TARGET_MAX_AREA: 最大坪數數字 (純數字字串)。
    - FILTER_KEYWORDS: 陣列，請從以下清單中挑選使用者提及的條件 (必須完全符合字眼)：
      ["整層住家", "獨立套房", "分租套房", "雅房", "有電梯", "有車位", "有陽台", "可養寵物", "可開伙", "排除頂樓加蓋", "有冷氣", "有洗衣機", "有冰箱", "有天然瓦斯", "電梯大樓", "公寓"]

    使用者需求：「{user_query}」
    
    請只輸出 JSON 格式的純文字，不要有任何 Markdown 標記 (如 ```json) 或其他解釋說明。
    """
    
    try:
        # 使用 gemini-1.5-flash，速度極快且適合這類解析任務
        model = genai.GenerativeModel('gemini-3-flash-preview')
        response = model.generate_content(prompt)
        
        # 清洗可能帶有的 Markdown 標記
        clean_text = response.text.strip().replace("```json", "").replace("```", "")
        parsed_config = json.loads(clean_text)
        print("✅ LLM 解析成功！得出的搜尋參數如下：")
        print(json.dumps(parsed_config, indent=4, ensure_ascii=False))
        return parsed_config
        
    except Exception as e:
        print(f"❌ LLM 解析失敗: {e}")
        # 若解析失敗，回傳一組預設的安全參數
        return {
            "TARGET_REGION": "1",
            "SEARCH_KEYWORD": "台北榮總",
            "TARGET_MIN_PRICE": "",
            "TARGET_MAX_PRICE": "50000",
            "TARGET_MIN_AREA": "15",
            "TARGET_MAX_AREA": "",
            "FILTER_KEYWORDS": ["整層住家", "有電梯"]
        }
# =====================================================

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            return []
    return []

def save_history(history_list):
    try:
        if len(history_list) > 1000:
            history_list = history_list[-1000:]
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history_list, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"❌ 儲存 {HISTORY_FILE} 失敗: {e}")

def send_discord_webhook(houses):
    if not houses or not DISCORD_WEBHOOK_URL:
        return
    print(f"\n🚀 準備將 {len(houses)} 筆資料推播至 Discord...")
    for i in range(0, len(houses), 10):
        chunk = houses[i:i+10]
        embeds = []
        for house in chunk:
            embeds.append({
                "title": f"🏠 {house['title']}",
                "url": house['link'],
                "description": f"💰 **價格**: {house['price']} 元/月\n📏 **坪數**: {house['area']} 坪",
                "color": 16748339  
            })
        payload = {
            "username": "NemoClaw 租屋雷達", 
            "content": f"🚨 發現 **{len(houses)}** 筆符合條件的全新物件！" if i == 0 else "",
            "embeds": embeds
        }
        try:
            requests.post(DISCORD_WEBHOOK_URL, json=payload)
        except Exception as e:
            print(f"  ❌ 呼叫 Discord API 時發生錯誤: {e}")

async def random_delay(min_sec=1, max_sec=3):
    await asyncio.sleep(random.uniform(min_sec, max_sec))

# ⚠️ 注意：main 函數現在接收 config 字典作為參數
async def main(config):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = await context.new_page()

        print("🚀 前往 591 租屋網列表頁...")
        target_region = str(config.get('TARGET_REGION', '1')).strip()
        search_url = f"https://rent.591.com.tw/list?region={target_region}"
        
        try:
            await page.goto(search_url, wait_until="networkidle")
            await random_delay(2, 4)

            search_keyword = str(config.get("SEARCH_KEYWORD", "")).strip()
            if search_keyword:
                print(f"⌨️  正在搜尋框主動輸入關鍵字：【{search_keyword}】 ...")
                search_input = page.locator('input[placeholder*="請輸入"], .search-input input, input[type="text"]').first
                await search_input.fill(search_keyword)
                await random_delay(1, 2)
                await search_input.press("Enter")
                await random_delay(3, 5)

            try:
                expand_btn = page.locator("text=展開選項").first
                if await expand_btn.is_visible():
                    await expand_btn.click()
                    await random_delay(1.5, 2.5) 
            except Exception:
                pass

            target_min_price = str(config.get("TARGET_MIN_PRICE", "")).strip()
            target_max_price = str(config.get("TARGET_MAX_PRICE", "")).strip()
            if target_min_price or target_max_price:
                print(f"\n💰 正在輸入自訂租金區間：{target_min_price} - {target_max_price} 元...")
                min_price_input = page.locator('input[placeholder="最低價"]').first
                max_price_input = page.locator('input[placeholder="最高價"]').first
                
                if target_min_price and await min_price_input.is_visible():
                    await min_price_input.fill(target_min_price)
                    await random_delay(0.5, 1)
                
                if target_max_price and await max_price_input.is_visible():
                    await max_price_input.fill(target_max_price)
                    await random_delay(0.5, 1)
                
                price_container = page.locator('.filter-input-container:has(input[placeholder="最低價"])')
                confirm_btn = price_container.locator('button:has-text("確定")')
                await confirm_btn.click()
                await random_delay(2.5, 4) 

            target_min_area = str(config.get("TARGET_MIN_AREA", "")).strip()
            target_max_area = str(config.get("TARGET_MAX_AREA", "")).strip()
            if target_min_area or target_max_area:
                print(f"\n📏 正在輸入自訂坪數區間：{target_min_area} - {target_max_area} 坪...")
                min_area_input = page.locator('input[placeholder="最小坪"]').first
                max_area_input = page.locator('input[placeholder="最大坪"]').first
                
                if target_min_area and await min_area_input.is_visible():
                    await min_area_input.fill(target_min_area)
                    await random_delay(0.5, 1)
                
                if target_max_area and await max_area_input.is_visible():
                    await max_area_input.fill(target_max_area)
                    await random_delay(0.5, 1)
                
                area_container = page.locator('.filter-input-container:has(input[placeholder="最小坪"])')
                confirm_btn = area_container.locator('button:has-text("確定")')
                await confirm_btn.click()
                await random_delay(2.5, 4)

            filter_keywords = config.get("FILTER_KEYWORDS", [])
            if filter_keywords:
                print("\n🖱️ 開始勾選進階篩選標籤...")
                for keyword in filter_keywords:
                    print(f"  ➡️ 嘗試點擊：【{keyword}】")
                    try:
                        locator = page.locator(f".filter-item:has-text('{keyword}')").first
                        if await locator.count() == 0:
                             locator = page.locator(f"label.t5-checkbox:has-text('{keyword}')").first

                        if await locator.count() > 0:
                            await locator.click(force=True)
                            await random_delay(1.5, 2.5)
                        else:
                            print(f"  ⚠️ 找不到包含【{keyword}】的元件")
                    except Exception as e:
                        print(f"  ❌ 點擊【{keyword}】時發生錯誤: {e}")
                
            print("\n✅ 篩選條件設定完畢，準備擷取最終結果...")

            # ================= 自動翻頁與抓取邏輯 =================
            MAX_PAGES = 5 
            all_houses_data = []

            for current_page in range(1, MAX_PAGES + 1):
                for _ in range(3):
                    await page.evaluate("window.scrollBy(0, 800)")
                    await random_delay(1, 2)

                houses_data = await page.evaluate('''() => {
                    const results = [];
                    const titleDivs = document.querySelectorAll('.item-info-title');
                    
                    titleDivs.forEach(titleDiv => {
                        const linkTag = titleDiv.querySelector('a.link');
                        if (!linkTag) return;

                        const title = linkTag.getAttribute('title') || linkTag.innerText;
                        const link = linkTag.href;

                        let currentParent = titleDiv;
                        let flexDiv = null;
                        for(let i = 0; i < 3; i++) {
                            currentParent = currentParent.parentElement;
                            if(currentParent) {
                                flexDiv = currentParent.querySelector('.item-info-flex');
                                if(flexDiv) break; 
                            }
                        }

                        let price_str = "";
                        let raw_text = titleDiv.innerText;

                        if (flexDiv) {
                            raw_text += " | " + flexDiv.innerText;
                            const priceNode = flexDiv.querySelector('.item-info-price strong');
                            if (priceNode) price_str = priceNode.innerText;
                        }

                        results.push({
                            title: title,
                            link: link,
                            price_str: price_str,
                            raw_text: raw_text
                        });
                    });
                    return results;
                }''')

                all_houses_data.extend(houses_data)

                next_btn = page.locator("span.navigator:has-text('下一頁')").first
                if await next_btn.count() > 0:
                    is_disabled = await next_btn.evaluate("el => el.classList.contains('disabled')")
                    if not is_disabled and current_page < MAX_PAGES:
                        await next_btn.click()
                        await random_delay(3, 5) 
                    else:
                        break
                else:
                    break
            # ====================================================

            results = []
            for house in all_houses_data:
                title = house['title']
                link = house['link']
                text = house['raw_text'].replace('\n', ' ') 
                
                price_clean = house['price_str'].replace(',', '').strip()
                price = int(price_clean) if price_clean.isdigit() else 0
                
                area_match = re.search(r'([\d\.]+)\s*坪', text)
                area = float(area_match.group(1)) if area_match else 0.0

                results.append({
                    "title": title,
                    "price": price,
                    "area": area,
                    "link": link
                })

            history_urls = load_history()
            new_results = []

            for res in results:
                if res['link'] not in history_urls:
                    new_results.append(res)
                    history_urls.append(res['link'])

            print(f"🧠 經過記憶比對，本次共有 {len(new_results)} 筆全新房源！\n")

            if len(new_results) > 0:
                send_discord_webhook(new_results)
                save_history(history_urls)
                print("💾 已更新 history.json 記憶檔。")
            else:
                print("😴 沒有新的房源，無需推播。")

        except Exception as e:
            print(f"❌ 發生錯誤: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    # 在這裡輸入你的自然語言需求！
    user_query = "幫我找台北榮總附近，租金最高五萬，坪數15坪以上，一定要有電梯和車位的整層住家，最好能排除頂樓加蓋。"
    
    # 1. 呼叫 LLM 進行解析
    parsed_config = parse_natural_language(user_query)
    
    # 2. 將解析結果餵給 Playwright 爬蟲
    asyncio.run(main(parsed_config))