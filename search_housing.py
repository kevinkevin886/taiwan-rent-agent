import asyncio
import random
import re
import requests
import os
import json
from playwright.async_api import async_playwright
from dotenv import load_dotenv

load_dotenv()
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
HISTORY_FILE = "history.json"

# ================= 搜尋條件設定區 =================
TARGET_REGION = "1"  # 1: 台北市, 3: 新北市
SEARCH_KEYWORD = "台大醫院" 
FILTER_KEYWORDS = ["整層住家", "有電梯"] 
TARGET_MIN_PRICE = "25000"
TARGET_MAX_PRICE = "100000"
TARGET_MIN_AREA = "15"
TARGET_MAX_AREA = ""
# =================================================

def load_history():
    """讀取歷史推播紀錄"""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ 讀取 {HISTORY_FILE} 失敗: {e}，將建立新紀錄。")
            return []
    return []

def save_history(history_list):
    """儲存歷史推播紀錄 (最多保留最新的 1000 筆避免檔案過大)"""
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
            response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
            if response.status_code in [200, 204]:
                print(f"  ✅ 成功推播 {len(chunk)} 筆資料到 Discord！")
            else:
                print(f"  ❌ 推播失敗：HTTP {response.status_code} - {response.text}")
        except Exception as e:
            print(f"  ❌ 呼叫 Discord API 時發生錯誤: {e}")

async def random_delay(min_sec=1, max_sec=3):
    await asyncio.sleep(random.uniform(min_sec, max_sec))

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = await context.new_page()

        print("🚀 前往 591 租屋網列表頁...")
        search_url = f"https://rent.591.com.tw/list?region={TARGET_REGION}"
        
        try:
            await page.goto(search_url, wait_until="networkidle")
            await random_delay(2, 4)

            # 1. 搜尋關鍵字
            print(f"⌨️  正在搜尋框主動輸入關鍵字：【{SEARCH_KEYWORD}】 ...")
            search_input = page.locator('input[placeholder*="請輸入"], .search-input input, input[type="text"]').first
            await search_input.fill(SEARCH_KEYWORD)
            await random_delay(1, 2)
            await search_input.press("Enter")
            print("⏳ 等待主搜尋結果載入...")
            await random_delay(3, 5)

            # 2. 點擊展開隱藏的進階選項
            try:
                expand_btn = page.locator("text=展開選項").first
                if await expand_btn.is_visible():
                    print("  🔽 發現「展開選項」按鈕，正在點擊以顯示所有隱藏條件...")
                    await expand_btn.click()
                    await random_delay(1.5, 2.5) 
            except Exception as e:
                print(f"  ⚠️ 展開按鈕檢查失敗: {e}")

            # 3. 輸入自訂租金區間並點擊專屬的「確定」
            if TARGET_MIN_PRICE or TARGET_MAX_PRICE:
                print(f"\n💰 正在輸入自訂租金區間：{TARGET_MIN_PRICE} - {TARGET_MAX_PRICE} 元...")
                min_price_input = page.locator('input[placeholder="最低價"]').first
                max_price_input = page.locator('input[placeholder="最高價"]').first
                
                if TARGET_MIN_PRICE and await min_price_input.is_visible():
                    await min_price_input.fill(TARGET_MIN_PRICE)
                    await random_delay(0.5, 1)
                
                if TARGET_MAX_PRICE and await max_price_input.is_visible():
                    await max_price_input.fill(TARGET_MAX_PRICE)
                    await random_delay(0.5, 1)
                
                price_container = page.locator('.filter-input-container:has(input[placeholder="最低價"])')
                confirm_btn = price_container.locator('button:has-text("確定")')
                
                await confirm_btn.click()
                print("  ✅ 成功點擊租金區間的「確定」按鈕！")
                await random_delay(2.5, 4) 

            # 4. 輸入自訂坪數區間並點擊專屬的「確定」
            if TARGET_MIN_AREA or TARGET_MAX_AREA:
                print(f"\n📏 正在輸入自訂坪數區間：{TARGET_MIN_AREA} - {TARGET_MAX_AREA} 坪...")
                min_area_input = page.locator('input[placeholder="最小坪"]').first
                max_area_input = page.locator('input[placeholder="最大坪"]').first
                
                if TARGET_MIN_AREA and await min_area_input.is_visible():
                    await min_area_input.fill(TARGET_MIN_AREA)
                    await random_delay(0.5, 1)
                
                if TARGET_MAX_AREA and await max_area_input.is_visible():
                    await max_area_input.fill(TARGET_MAX_AREA)
                    await random_delay(0.5, 1)
                
                area_container = page.locator('.filter-input-container:has(input[placeholder="最小坪"])')
                confirm_btn = area_container.locator('button:has-text("確定")')
                
                await confirm_btn.click()
                print("  ✅ 成功點擊坪數區間的「確定」按鈕！")
                await random_delay(2.5, 4)

            # 5. 勾選進階核取條件
            if FILTER_KEYWORDS:
                print("\n🖱️ 開始勾選進階篩選標籤...")
                for keyword in FILTER_KEYWORDS:
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
                print(f"📄 正在抓取第 {current_page} 頁資料...")

                for _ in range(3):
                    await page.evaluate("window.scrollBy(0, 800)")
                    await random_delay(1, 2)

                print("  🎯 啟動視覺抓取...")
                
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
                print(f"  ✅ 本頁擷取了 {len(houses_data)} 個卡片。")

                # 尋找「下一頁」按鈕
                next_btn = page.locator("span.navigator:has-text('下一頁')").first
                
                if await next_btn.count() > 0:
                    is_disabled = await next_btn.evaluate("el => el.classList.contains('disabled')")
                    
                    if not is_disabled and current_page < MAX_PAGES:
                        print(f"  👉 點擊「下一頁」，準備前往第 {current_page + 1} 頁...\n")
                        await next_btn.click()
                        await random_delay(3, 5) 
                    elif is_disabled:
                        print("  🛑 「下一頁」按鈕已禁用，代表已達最後一頁。")
                        break
                    else:
                        print(f"  🛑 已達到設定的最大翻頁限制 ({MAX_PAGES} 頁)。")
                        break
                else:
                    print("  🛑 畫面上找不到「下一頁」按鈕，可能只有一頁。")
                    break
            # ====================================================

            print(f"\n🎉 爬取結束！總共擷取 {len(all_houses_data)} 個原始租屋卡片！\n")
            
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

            # ================= 記憶系統比對區塊 =================
            history_urls = load_history()
            new_results = []

            for res in results:
                if res['link'] not in history_urls:
                    new_results.append(res)
                    history_urls.append(res['link'])

            print(f"🧠 經過記憶比對，扣除已推播過的物件，本次共有 {len(new_results)} 筆全新房源！\n")

            for idx, res in enumerate(new_results, 1):
                print(f"🏠 [{idx}] {res['title']}")
                print(f"💰 價格: {res['price']} 元/月 | 📏 坪數: {res['area']} 坪")
                print(f"🔗 連結: {res['link']}")
                print("-" * 50)

            if len(new_results) > 0:
                send_discord_webhook(new_results)
                save_history(history_urls)
                print("💾 已更新 history.json 記憶檔。")
            else:
                print("😴 沒有新的房源，無需推播。")
            # ====================================================

        except Exception as e:
            print(f"❌ 發生錯誤: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())