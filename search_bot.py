import asyncio
import random
import re
import os
import json
import discord # 👈 新增 discord 模組
from discord.ext import commands
from playwright.async_api import async_playwright
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
HISTORY_FILE = "history.json"
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# ================= 記憶系統與 LLM 解析 (保持不變) =================
def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
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

def parse_natural_language(user_query: str) -> dict:
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
        model = genai.GenerativeModel('gemini-3-flash-preview')
        response = model.generate_content(prompt)
        clean_text = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(clean_text)
    except Exception as e:
        print(f"❌ LLM 解析失敗: {e}")
        return {"TARGET_REGION": "1", "SEARCH_KEYWORD": "", "TARGET_MIN_PRICE": "", "TARGET_MAX_PRICE": "", "TARGET_MIN_AREA": "", "TARGET_MAX_AREA": "", "FILTER_KEYWORDS": []}

async def random_delay(min_sec=1, max_sec=3):
    await asyncio.sleep(random.uniform(min_sec, max_sec))

# ================= 核心爬蟲函數 (移除原本的 webhook 發送，改為回傳結果) =================
async def run_scraper(config):
    new_results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = await context.new_page()

        target_region = str(config.get('TARGET_REGION', '1')).strip()
        search_url = f"https://rent.591.com.tw/list?region={target_region}"
        
        try:
            await page.goto(search_url, wait_until="networkidle")
            await random_delay(2, 4)

            search_keyword = str(config.get("SEARCH_KEYWORD", "")).strip()
            if search_keyword:
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
                for keyword in filter_keywords:
                    try:
                        locator = page.locator(f".filter-item:has-text('{keyword}')").first
                        if await locator.count() == 0:
                             locator = page.locator(f"label.t5-checkbox:has-text('{keyword}')").first
                        if await locator.count() > 0:
                            await locator.click(force=True)
                            await random_delay(1.5, 2.5)
                    except Exception:
                        pass
                
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
                        results.push({title: title, link: link, price_str: price_str, raw_text: raw_text});
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

            results = []
            for house in all_houses_data:
                title = house['title']
                link = house['link']
                text = house['raw_text'].replace('\n', ' ') 
                price_clean = house['price_str'].replace(',', '').strip()
                price = int(price_clean) if price_clean.isdigit() else 0
                area_match = re.search(r'([\d\.]+)\s*坪', text)
                area = float(area_match.group(1)) if area_match else 0.0
                results.append({"title": title, "price": price, "area": area, "link": link})

            history_urls = load_history()

            for res in results:
                if res['link'] not in history_urls:
                    new_results.append(res)
                    history_urls.append(res['link'])

            if len(new_results) > 0:
                save_history(history_urls)

        except Exception as e:
            print(f"❌ 爬蟲發生錯誤: {e}")
        finally:
            await browser.close()
            return new_results

# ================= Discord Bot 設定區 =================
# 設定 Bot 的權限
intents = discord.Intents.default()
intents.message_content = True 
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'✅ Bot 已上線！目前的身份是：{bot.user}')
    print('💡 請在 Discord 頻道中輸入例如：!找房 幫我找台北榮總附近，租金最高五萬...')

# 設定啟動爬蟲的指令
@bot.command(name="找房")
async def find_house(ctx, *, query: str):
    """
    當你在 Discord 輸入：!找房 <你的條件> 時會觸發這個函數
    """
    await ctx.send(f"🔍 收到指令！正在請 LLM 解析您的需求...\n💬 您的需求：「{query}」")
    
    # 1. 呼叫 LLM 進行解析 (這是同步執行的)
    parsed_config = parse_natural_language(query)
    await ctx.send(f"⚙️ 解析完成！正在為您啟動 591 爬蟲雷達，這可能需要 1~2 分鐘，請稍候...")
    
    # 2. 啟動 Playwright 爬蟲
    new_houses = await run_scraper(parsed_config)
    
    # 3. 把爬到的結果轉成 Discord 卡片發送回頻道
    if not new_houses:
        await ctx.send("😴 報告！目前沒有發現符合條件的全新房源。")
        return

    # 分批發送 (Discord 限制一次最多 10 個 embeds)
    for i in range(0, len(new_houses), 10):
        chunk = new_houses[i:i+10]
        embeds = []
        for house in chunk:
            # 建立精美的卡片
            embed = discord.Embed(
                title=f"🏠 {house['title']}",
                url=house['link'],
                description=f"💰 **價格**: {house['price']} 元/月\n📏 **坪數**: {house['area']} 坪",
                color=0xFF6600
            )
            embeds.append(embed)
            
        content_msg = f"🚨 發現 **{len(new_houses)}** 筆符合條件的全新物件！" if i == 0 else ""
        await ctx.send(content=content_msg, embeds=embeds)

if __name__ == "__main__":
    if not DISCORD_BOT_TOKEN:
        print("❌ 找不到 DISCORD_BOT_TOKEN！請確認已加入 .env 檔案中。")
    else:
        # 啟動 Discord Bot (這個指令會佔用終端機一直運行)
        bot.run(DISCORD_BOT_TOKEN)