import os
import requests
import json
from dotenv import load_dotenv
from openai import OpenAI
import yfinance as yf

# โหลด API Key จากไฟล์ .env (หรือ key.env)
load_dotenv("key.env")
API_KEY = os.getenv("OPENROUTER_API_KEY")

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=API_KEY,
)

# ฟังก์ชันสำหรับดึงราคาหุ้น
def get_stock_price(tickers):
    # ป้องกันกรณี LLM ส่งมาเป็น String เผื่อหลุดจาก Prompt
    if isinstance(tickers, str):
        tickers = [tickers]
        
    print(f"กำลังเรียกใช้ get_stock_price() ด้วย Tickers: {tickers}")
    results = []
    
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            price = stock.info.get('currentPrice')
            if price:
                print(f"ดึงราคา {ticker} สำเร็จ: {price}")
                results.append(f"- ราคาหุ้น {ticker.upper()} ล่าสุดคือ {price:.2f}")
            else:
                print(f"ไม่พบราคาหุ้น {ticker} ใน info")
                results.append(f"- ไม่พบข้อมูลราคาหุ้น {ticker.upper()}")
        except Exception as e:
            results.append(f"- ไม่สามารถดึงข้อมูลหุ้น {ticker.upper()} ได้ ({e})")
            
    return "\n".join(results)

# ฟังก์ชันสำหรับดึงสภาพอากาศ
def get_weather(city):
    print(f"กำลังเรียกใช้ get_weather() ด้วย City: '{city}'")
    try:
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&language=en&format=json"
        print(f"ยิง API Geocoding ไปที่: {geo_url}")
        geo_res = requests.get(geo_url).json()

        if "results" in geo_res and len(geo_res["results"]) > 0:
            lat = geo_res["results"][0]["latitude"]
            lon = geo_res["results"][0]["longitude"]
            official_name = geo_res["results"][0]["name"]
            print(f"เจอ พิกัด: ({lat}, {lon}) สำหรับ {official_name}")

            weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
            weather_res = requests.get(weather_url).json()
            temp = weather_res["current_weather"]["temperature"]

            print(f"อุณหภูมิที่ได้: {temp}°C")
            return f"อุณหภูมิปัจจุบันใน {official_name} คือ {temp}°C"
        
        print(f"ไม่พบผลลัพธ์เมือง {city} จาก Geocoding API")
        return f"ไม่พบข้อมูลสภาพอากาศของเมือง {city}"
    except Exception as e:
        print(f"เกิด Exception ใน get_weather: {e}")
        return f"ไม่สามารถดึงข้อมูลสภาพอากาศของ {city} ได้"

# Prompt ให้ LLM วิเคราะห์ Intent และตอบกลับในรูปแบบ JSON
router_system_prompt = """คุณคือตัววิเคราะห์ความจำนงของผู้ใช้ (Intent Classifier)
จงวิเคราะห์ข้อความของผู้ใช้ แล้วตอบกลับเป็น JSON เท่านั้น (ห้ามใส่ Markdown Codeblock)

การตัดสินใจเลือก action:
1. "get_stock_price": เมื่อผู้ใช้ถามคำถามเพื่อขอทราบราคาหุ้น ตลาดหุ้นจริงๆ หรือขอคำแนะนำ/วิเคราะห์/เปรียบเทียบการลงทุนในหุ้น 1 ตัวหรือหลายตัวพร้อมกัน (ให้ดึงสัญลักษณ์ ticker ทั้งหมดใส่ใน list เช่น ["AAPL"], ["AAPL", "TSLA", "PTT.BK"])
2. "get_weather": เมื่อผู้ใช้ถามคำถามเพื่อขอทราบอุณหภูมิ/พยากรณ์อากาศจริงๆ หรือถามคำถามที่ต้องใช้สภาพอากาศปัจจุบันประกอบการตัดสินใจ (เช่น ออกไปวิ่งได้ไหม, ต้องพกร่มไหม) โดยให้ระบุชื่อเมือง ถ้าเป็นภาษาไทยให้เปลี่ยนเป็นภาษาอังกฤษ (เช่น "กรุงเทพ" เป็น "Bangkok", "โตเกียว" เป็น "Tokyo")
3. "chat": คำถามหรือข้อความอื่นๆทั้งหมด คำถามกำกวม (เช่น "ที่นี่อากาศเป็นยังไง") หรือเปรียบปรยโดยไม่ต้องการข้อมูล API ข้างต้น (เช่น "วันนี้กรุงเทพอากาศดีนะ ไม่เห็นมีฝนตามพยากรณ์เลย")

หลักการกำหนด "need_analysis" (true/false) สำหรับ get_stock_price และ get_weather:
- true: เมื่อผู้ใช้ถามคำถามเชิงวิเคราะห์ ขอคำแนะนำ Decision-making หรือมีคำถามต่อยอด (เช่น "อากาศกรุงเทพตอนนี้เป็นยังไง ออกไปซื้อของได้ไหม", "หุ้น PTT ราคานี้ควรซื้อไหม")
- false: เมื่อผู้ใช้ต้องการทราบเพียง "ข้อมูลตัวเลข/สภาพอากาศตรงๆ" (เช่น "ราคาหุ้น AAPL เท่าไหร่", "ตอนนี้สภาพอากาศกรุงเทพเป็นยังไง")

รูปแบบโครงสร้าง JSON:
- ถ้า get_stock_price: {"action": "get_stock_price", "tickers": ["TICKER1", "TICKER2"]}
- ถ้า get_weather: {"action": "get_weather", "city": "ชื่อเมือง"}
- ถ้า chat: {"action": "chat"}
"""

# Prompt วิเคราะห์ข้อมูลจาก API ร่วมกับคำถามผู้ใช้
analyze_system_prompt = """คุณคือผู้ช่วย AI อัจฉริยะ 
จงนำข้อมูลจริงที่ได้จากระบบ API มาตอบคำถามและวิเคราะห์ต่อยอดตามที่ผู้ใช้ต้องการอย่างมีเหตุผลและเป็นธรรมชาติ
- หากผู้ใช้ถามว่าเหมาะจะออกไปทำกิจกรรมไหม (เช่น วิ่ง, ออกกำลังกาย) ให้วิเคราะห์จากอุณหภูมิและสภาพอากาศที่ได้
- หากผู้ใช้ถามเรื่องแนวโน้มการลงทุน ให้ระบุราคาปัจจุบันและให้คำแนะนำหลักการลงทุนเบื้องต้นแบบเป็นกลาง
- หากผู้ใช้ถามเปรียบเทียบหุ้นหลายตัว ให้สรุปข้อมูลราคาของแต่ละตัวและวิเคราะห์เปรียบเทียบอย่างเป็นกลาง
- หากข้อมูลจริงที่ได้จากระบบ API ตอบคำถามครบถ้วนแล้ว คุณไม่จำเป็นต้องวิเคราะห์ต่อ"""

# ประวัติการสนทนา
messages_history = []
MAX_HISTORY = 10  # เก็บย้อนหลังสูงสุด 10 ข้อความ (5 คู่ สนทนา) เพื่อควบคุม Token

while True:
    user_input = input("User: ")

    if user_input.strip().lower() in ["exit", "quit", "ออก"]:
        print("Exit")
        break

    if user_input.strip().lower() in ["clear", "clear history", "ล้างประวัติ"]:
        messages_history.clear()
        print("ระบบ: ล้างประวัติการสนทนาเรียบร้อยแล้ว")
        continue

    if not user_input.strip():
        continue

    print(f"กำลังส่งคำถามไปยัง LLM เพื่อวิเคราะห์")

    # รวม System Prompt + ประวัติการสนทนา + ข้อความปัจจุบันส่งไปวิเคราะห์ Intent
    router_messages = [{"role": "system", "content": router_system_prompt}] + messages_history[-MAX_HISTORY:] + [{"role": "user", "content": user_input}]

    # ส่งคำถามให้ LLM วิเคราะห์ Intent
    res = client.chat.completions.create(
        model="openrouter/free",
        messages=router_messages,
        response_format={"type": "json_object"}
    )

    raw_response = res.choices[0].message.content
    print(f"Raw Response จาก LLM:\n{raw_response}")

    try:
        data = json.loads(raw_response)
        action = data.get("action")
        print(f"Action ที่ถอดได้จาก JSON: '{action}'")

        final_reply = ""

        # ตรวจสอบเงื่อนไขแล้วเรียกใช้ฟังก์ชันตามที่ LLM ระบุ
        if action in ["get_stock_price", "get_weather"]:
            if action == "get_stock_price":
                # รับค่าเป็น List จาก key "tickers"
                ticker = data.get("tickers", [])
                print(f"ตรวจพบ Parameter 'ticker': {ticker}")
                api_result = get_stock_price(ticker)
            else:
                city = data.get("city")
                print(f"ตรวจพบ Parameter 'city': {city}")
                api_result = get_weather(city)

            # ตรวจสอบว่าผู้ใช้ต้องการการวิเคราะห์ต่อยอดหรือไม่
            need_analysis = data.get("need_analysis", False)

            # ตรวจสอบว่าต้องส่งเข้า analyze_system_prompt หรือไม่
            if need_analysis:
                # กรณีต้องการคำแนะนำ/วิเคราะห์ต่อยอด -> ส่งหา LLM ร่วมกับ analyze_system_prompt
                print("คำถามต้องการการวิเคราะห์ต่อยอด -> กำลังส่งให้ LLM ประมวลผล")
                try:
                    # ส่งประวัติแชทร่วมกับการวิเคราะห์ข้อมูล API
                    analysis_messages = (
                        [{"role": "system", "content": analyze_system_prompt}]
                        + messages_history[-MAX_HISTORY:]
                        + [{"role": "user", "content": f"คำถามผู้ใช้: {user_input}\nข้อมูลจริงจาก API: {api_result}"}]
                    )
                    analyze_res = client.chat.completions.create(
                        model="openrouter/free",
                        messages=analysis_messages,
                        timeout=15
                    )
                    final_reply = analyze_res.choices[0].message.content
                    print(f"AI: {final_reply}")
                except Exception as e:
                    print(f"ไม่สามารถวิเคราะห์ต่อยอดได้เนื่องจาก: {e}")
                    final_reply = api_result
                    print(f"AI (ข้อมูลสำรอง): {api_result}")
            else:
                # กรณีแค่ต้องการข้อมูลดิบตรงๆ -> พิมพ์ผลลัพธ์ API ได้เลยโดยข้าม analyze_system_prompt
                print("คำถามต้องการแค่ข้อมูลตรงๆ -> ข้ามการวิเคราะห์")
                final_reply = api_result
                print(f"AI: {api_result}")

        else:
            # กรณี action == "chat" หรือ action อื่นๆ ให้ส่งหา LLM เพื่อแชทสนทนาตามปกติ
            print("ไม่ได้เรียกใช้ API -> ส่งตอบแชททั่วไป")
            chat_messages = (
                [{"role": "system", "content": "คุณคือผู้ช่วย AI อัจฉริยะ ตอบคำถามผู้ใช้อย่างสุภาพและเป็นธรรมชาติ"}]
                + messages_history[-MAX_HISTORY:]
                + [{"role": "user", "content": user_input}]
            )
            chat_res = client.chat.completions.create(
                model="openrouter/free",
                messages=chat_messages
            )
            final_reply = chat_res.choices[0].message.content
            print(f"AI: {final_reply}")

        # อัปเดตประวัติการสนทนา
        messages_history.append({"role": "user", "content": user_input})
        messages_history.append({"role": "assistant", "content": final_reply})

    except json.JSONDecodeError as e:
        print(f"JSONDecodeError: อ่าน JSON ไม่สำเร็จ - {e}")
        print("AI: เกิดข้อผิดพลาดในการอ่านข้อมูลจาก LLM")