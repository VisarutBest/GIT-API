import os
import requests
import json
from dotenv import load_dotenv
from openai import OpenAI
import yfinance as yf
import csv
from datetime import datetime

CSV_FILE = "test_logs.csv"

def log_to_csv(user_input, action, parameters, need_analysis, api_result, final_reply, status="SUCCESS"):
    file_exists = os.path.isfile(CSV_FILE)
    
    # ใช้ encoding='utf-8-sig' เพื่อให้เปิดใน Excel แล้วภาษาไทยไม่เพี้ยน
    with open(CSV_FILE, mode="a", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        
        # สร้าง Header อัตโนมัติถ้ายังไม่มีไฟล์
        if not file_exists:
            writer.writerow([
                "Timestamp", "User_Input", "Detected_Action", 
                "Parameters", "Need_Analysis", "API_Result", 
                "Final_Reply", "Status"
            ])
            
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            user_input,
            action,
            json.dumps(parameters, ensure_ascii=False),
            need_analysis,
            api_result,
            final_reply,
            status
        ])

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
def get_weather(cities):
    if isinstance(cities, str):
        cities = [cities]

    print(f"กำลังเรียกใช้ get_weather() ด้วย Cities: {cities}")
    results = []

    for city in cities:
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

                print(f"ดึงอุณหภูมิ {official_name} สำเร็จ: {temp}°C")
                results.append(f"- อุณหภูมิปัจจุบันใน {official_name} คือ {temp}°C")
            
            else:
                results.append(f"- ไม่พบข้อมูลสภาพอากาศของเมือง {city}")
        except Exception as e:
            results.append(f"- ไม่สามารถดึงข้อมูลสภาพอากาศของ {city} ได้ ({e})")
    
    return "\n".join(results)

# Prompt ให้ LLM วิเคราะห์ Intent และตอบกลับในรูปแบบ JSON
router_system_prompt = """คุณคือตัววิเคราะห์ความจำนงของผู้ใช้ (Intent Classifier)
จงวิเคราะห์ข้อความของผู้ใช้ แล้วตอบกลับเป็น JSON เท่านั้น (ห้ามใส่ Markdown Codeblock)

คุณสามารถเลือกเรียกใช้ได้หลาย action พร้อมกันหากผู้ใช้ถามหลายเรื่องในประโยคเดียว โดยใส่ไว้ใน list "tasks":
1. "get_stock_price": เมื่อผู้ใช้ถามคำถามเพื่อขอทราบราคาหุ้น ตลาดหุ้นจริงๆ หรือขอคำแนะนำ/วิเคราะห์/เปรียบเทียบการลงทุนในหุ้น 1 ตัวหรือหลายตัวพร้อมกัน (ให้ดึงสัญลักษณ์ ticker ทั้งหมดใส่ใน list เช่น ["AAPL"], ["AAPL", "TSLA", "PTT.BK"])
2. "get_weather": เมื่อผู้ใช้ถามคำถามเพื่อขอทราบอุณหภูมิ/พยากรณ์อากาศจริงๆ หรือถามคำถามที่ต้องใช้สภาพอากาศปัจจุบันประกอบการตัดสินใจ (เช่น ออกไปวิ่งได้ไหม, ต้องพกร่มไหม) โดยให้ระบุชื่อเมือง ถ้าเป็นภาษาไทยให้เปลี่ยนเป็นภาษาอังกฤษ (เช่น "กรุงเทพ" เป็น "Bangkok", "โตเกียว" เป็น "Tokyo") แล้วดึงชื่อเมืองมาใส่ใน list (เช่น ["Bangkok", "Tokyo"])
3. หากเป็นคำถามหรือข้อความอื่นๆทั้งหมด คำถามกำกวม (เช่น "ที่นี่อากาศเป็นยังไง") หรือเปรียบปรยโดยไม่ต้องการข้อมูล API ข้างต้น (เช่น "วันนี้กรุงเทพอากาศดีนะ ไม่เห็นมีฝนตามพยากรณ์เลย") ให้ส่ง "tasks": [] (list ว่าง)

หลักการกำหนด "need_analysis" (true/false) สำหรับ get_stock_price และ get_weather:
- true: เมื่อผู้ใช้ถามคำถามเชิงวิเคราะห์ ขอคำแนะนำ Decision-making หรือมีคำถามต่อยอด (เช่น "อากาศกรุงเทพตอนนี้เป็นยังไง ออกไปซื้อของได้ไหม", "หุ้น PTT ราคานี้ควรซื้อไหม")
- false: เมื่อผู้ใช้ต้องการทราบเพียง "ข้อมูลตัวเลข/สภาพอากาศตรงๆ" (เช่น "ราคาหุ้น AAPL เท่าไหร่", "ตอนนี้สภาพอากาศกรุงเทพเป็นยังไง")

รูปแบบโครงสร้าง JSON (ต้องมี key "tasks" และ "need_analysis" เสมอ):
- ตัวอย่างถามทั้งหุ้นและอากาศ: 
  {"tasks": [{"action": "get_stock_price", "tickers": ["AAPL"]}, {"action": "get_weather", "cities": ["Bangkok"]}], "need_analysis": false}
- ตัวอย่างถามอย่างเดียว: 
  {"tasks": [{"action": "get_weather", "cities": ["Tokyo"]}], "need_analysis": true}
- ตัวอย่างแชททั่วไป: 
  {"tasks": [], "need_analysis": false}
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

if __name__ == "__main__":
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
            tasks = data.get("tasks", [])
            need_analysis = data.get("need_analysis", False)
            print(f"Tasks ที่ถอดได้จาก JSON: '{tasks}'")

            final_reply = ""
        
            # ถ้ามีรายการใน tasks ให้วนลูปรันทุกฟังก์ชันที่ถูกเรียก
            if tasks:
                api_results = []
                
                for task in tasks:
                    action = task.get("action")
                    if action == "get_stock_price":
                        tickers = task.get("tickers", [])
                        print(f"ตรวจพบ Parameter 'ticker': {tickers}")
                        if tickers:
                            api_results.append(get_stock_price(tickers))
                            
                    elif action == "get_weather":
                        # รองรับทั้ง key "cities" (ใหม่) และ "city" (เผื่อ LLM หลุดส่งแบบเก่า)
                        cities = task.get("cities") or task.get("city")
                        print(f"ตรวจพบ Parameter 'city': {cities}")
                        if cities:
                            api_results.append(get_weather(cities))

                # รวมผลลัพธ์จากทุก API เข้าด้วยกัน
                combined_api_result = "\n".join(api_results)

                # ตรวจสอบว่าต้องส่งเข้า analyze_system_prompt หรือไม่
                if need_analysis:
                    # กรณีต้องการคำแนะนำ/วิเคราะห์ต่อยอด -> ส่งหา LLM ร่วมกับ analyze_system_prompt
                    print("คำถามต้องการการวิเคราะห์ต่อยอด -> กำลังส่งให้ LLM ประมวลผล")
                    try:
                        # ส่งประวัติแชทร่วมกับการวิเคราะห์ข้อมูล API
                        analysis_messages = (
                            [{"role": "system", "content": analyze_system_prompt}]
                            + messages_history[-MAX_HISTORY:]
                            + [{"role": "user", "content": f"คำถามผู้ใช้: {user_input}\nข้อมูลจริงจาก API: {combined_api_result}"}]
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
                        final_reply = combined_api_result
                        print(f"AI (ข้อมูลสำรอง): {combined_api_result}")
                else:
                    # กรณีแค่ต้องการข้อมูลดิบตรงๆ -> พิมพ์ผลลัพธ์ API ได้เลยโดยข้าม analyze_system_prompt
                    print("คำถามต้องการแค่ข้อมูลตรงๆ -> ข้ามการวิเคราะห์")
                    final_reply = combined_api_result
                    print(f"AI: {combined_api_result}")

            # กรณี tasks ว่าง ([]) ให้ตอบแชททั่วไป
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

            params = data.get("tickers") or data.get("cities") or ""
            api_out = combined_api_result if tasks in ["get_stock_price", "get_weather"] else ""
            need_ana = data.get("need_analysis", False)

            log_to_csv(user_input, tasks, params, need_ana, api_out, final_reply, status="SUCCESS")

            # อัปเดตประวัติการสนทนา
            messages_history.append({"role": "user", "content": user_input})
            messages_history.append({"role": "assistant", "content": final_reply})

        except json.JSONDecodeError as e:
            print(f"JSONDecodeError: อ่าน JSON ไม่สำเร็จ - {e}")
            print("AI: เกิดข้อผิดพลาดในการอ่านข้อมูลจาก LLM")
            log_to_csv(user_input, "ERROR", "", False, "", raw_response, status="JSON_ERROR")