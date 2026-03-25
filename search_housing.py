import asyncio
import random
import re
from playwright.async_api import async_playwright

TARGET_REGION = "1"  # 1: 台北市, 3: 新北市
SEARCH_KEYWORD = "台北榮總" 

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

            print(f"⌨️  正在搜尋框主動輸入關鍵字：【{SEARCH_KEYWORD}】 ...")
            search_input = page.locator('input[placeholder*="請輸入"], .search-input input, input[type="text"]').first
            await search_input.fill(SEARCH_KEYWORD)
            await random_delay(1, 2)
            await search_input.press("Enter")
            
            print("⏳ 等待網頁載入搜尋結果...")
            await random_delay(5, 7)

            for _ in range(3):
                await page.evaluate("window.scrollBy(0, 800)")
                await random_delay(1, 2)

            print("🎯 啟動精準打擊，使用向上查找法定位資料...")
            
            houses_data = await page.evaluate('''() => {
                const results = [];
                const titleDivs = document.querySelectorAll('.item-info-title');
                
                titleDivs.forEach(titleDiv => {
                    const linkTag = titleDiv.querySelector('a.link');
                    if (!linkTag) return;

                    const title = linkTag.getAttribute('title') || linkTag.innerText;
                    const link = linkTag.href;

                    // 【修正點】：從標題開始往外層(父節點)找，最多找3層，確保一定能包住 flex 區塊
                    let currentParent = titleDiv;
                    let flexDiv = null;
                    for(let i = 0; i < 3; i++) {
                        currentParent = currentParent.parentElement;
                        if(currentParent) {
                            flexDiv = currentParent.querySelector('.item-info-flex');
                            if(flexDiv) break; // 找到了就跳出迴圈
                        }
                    }

                    let price_str = "";
                    let raw_text = titleDiv.innerText;

                    if (flexDiv) {
                        raw_text += " | " + flexDiv.innerText;
                        
                        // 精準抓取價格節點
                        const priceNode = flexDiv.querySelector('.item-info-price strong');
                        if (priceNode) {
                            price_str = priceNode.innerText;
                        }
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

            print(f"\n✅ 成功從畫面上擷取到 {len(houses_data)} 個真實租屋卡片！\n")
            
            results = []
            for house in houses_data:
                title = house['title']
                link = house['link']
                text = house['raw_text'].replace('\n', ' ') 
                
                # 清洗價格
                price_clean = house['price_str'].replace(',', '').strip()
                price = int(price_clean) if price_clean.isdigit() else 0
                
                # 解析坪數
                area_match = re.search(r'([\d\.]+)\s*坪', text)
                area = float(area_match.group(1)) if area_match else 0.0

                results.append({
                    "title": title,
                    "price": price,
                    "area": area,
                    "link": link,
                    "raw_text": text 
                })

            print(f"🎯 總共列出 {len(results)} 筆物件 (無條件全抓)：\n")
            for idx, res in enumerate(results, 1):
                print(f"🏠 [{idx}] {res['title']}")
                print(f"💰 價格: {res['price']} | 📏 坪數: {res['area']}")
                print(f"🔗 連結: {res['link']}")
                print(f"📝 擷取文字: {res['raw_text'][:120]}...") 
                print("-" * 50)

        except Exception as e:
            print(f"❌ 發生錯誤: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())