import asyncio
import random
import re
import requests
import os
from playwright.async_api import async_playwright
from dotenv import load_dotenv
load_dotenv()

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# ================= 搜尋條件設定區 =================
TARGET_REGION = "1"  
SEARCH_KEYWORD = "台大醫院" 
FILTER_KEYWORDS = ["整層住家", "有車位", "排除頂樓加蓋"] 
TARGET_MIN_PRICE = "15000"
TARGET_MAX_PRICE = "50000"
TARGET_MIN_AREA = "15"
TARGET_MAX_AREA = ""
# =================================================

def send_discord_webhook(houses):
    if not houses or not DISCORD_WEBHOOK_URL:
        return

    print(f"\n🚀 準備將 {len(houses)} 筆資料推播至 Discord...")
    
    # Discord 限制每次請求最多 10 個 embeds，所以我們需要把結果「切塊」
    for i in range(0, len(houses), 10):
        chunk = houses[i:i+10]
        embeds = []
        
        for house in chunk:
            embeds.append({
                "title": f"🏠 {house['title']}",
                "url": house['link'],
                "description": f"💰 **價格**: {house['price']} 元/月\n📏 **坪數**: {house['area']} 坪",
                "color": 16748339  # 這是 591 標誌性的亮橘色
            })

        payload = {
            "username": "NemoClaw 租屋雷達", # 發送者名稱
            "content": f"🚨 發現 **{len(houses)}** 筆符合條件的物件！" if i == 0 else "",
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
                
                # 🎯 尋找包含「最低價」輸入框的那個容器，然後點擊裡面的「確定」按鈕
                price_container = page.locator('.filter-input-container:has(input[placeholder="最低價"])')
                confirm_btn = price_container.locator('button:has-text("確定")')
                
                # Playwright 會自動等待按鈕出現 (因為我們剛剛填了數字，Vue 會渲染它)
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
                
                # 🎯 尋找包含「最小坪」輸入框的那個容器，然後點擊裡面的「確定」按鈕
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
                print("✅ 篩選條件設定完畢，準備擷取最終結果...\n")

            # 模擬向下滾動，載入圖片與隱藏卡片
            for _ in range(3):
                await page.evaluate("window.scrollBy(0, 800)")
                await random_delay(1, 2)

            print("🎯 啟動精準打擊，抓取畫面上所有的租屋卡片...")
            
            # --- 視覺抓取與 DOM 解析邏輯 (保持不變) ---
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

            print(f"\n✅ 成功擷取 {len(houses_data)} 個符合所有條件的租屋卡片！\n")
            
            results = []
            for house in houses_data:
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

            for idx, res in enumerate(results, 1):
                print(f"🏠 [{idx}] {res['title']}")
                print(f"💰 價格: {res['price']} 元/月 | 📏 坪數: {res['area']} 坪")
                print(f"🔗 連結: {res['link']}")
                print("-" * 50)

            # 👈 在這裡加入 Discord 推播！
            if len(results) > 0:
                send_discord_webhook(results)

        except Exception as e:
            print(f"❌ 發生錯誤: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())