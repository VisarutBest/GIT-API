import json
import pandas as pd
from main import (
    client,
    router_system_prompt,
    analyze_system_prompt,
    get_stock_price,
    get_weather,
    log_to_csv,
)


def run_single_prompt(user_input: str) -> str:
    router_messages = [
        {"role": "system", "content": router_system_prompt},
        {"role": "user", "content": user_input},
    ]

    res = client.chat.completions.create(
        model="openrouter/free",
        messages=router_messages,
        response_format={"type": "json_object"},
    )
    raw_response = res.choices[0].message.content

    try:
        data = json.loads(raw_response)
        tasks = data.get("tasks", [])
        need_analysis = data.get("need_analysis", False)

        if tasks:
            api_results = []
            params_list = []

            for task in tasks:
                action = task.get("action")
                if action == "get_stock_price":
                    tickers = task.get("tickers", [])
                    if tickers:
                        params_list.append({"tickers": tickers})
                        api_results.append(get_stock_price(tickers))
                elif action == "get_weather":
                    cities = task.get("cities") or task.get("city")
                    if cities:
                        params_list.append({"cities": cities})
                        api_results.append(get_weather(cities))

            combined_api_result = "\n".join(api_results)

            if need_analysis:
                analysis_messages = [
                    {"role": "system", "content": analyze_system_prompt},
                    {
                        "role": "user",
                        "content": f"คำถามผู้ใช้: {user_input}\nข้อมูลจริงจาก API: {combined_api_result}",
                    },
                ]
                analyze_res = client.chat.completions.create(
                    model="openrouter/free",
                    messages=analysis_messages,
                    timeout=15,
                )
                final_reply = analyze_res.choices[0].message.content
            else:
                final_reply = combined_api_result

            log_to_csv(
                user_input,
                tasks,
                params_list,
                need_analysis,
                combined_api_result,
                final_reply,
                status="SUCCESS",
            )
            return final_reply

        chat_messages = [
            {
                "role": "system",
                "content": "คุณคือผู้ช่วย AI อัจฉริยะ ตอบคำถามผู้ใช้อย่างสุภาพและเป็นธรรมชาติ",
            },
            {"role": "user", "content": user_input},
        ]
        chat_res = client.chat.completions.create(
            model="openrouter/free",
            messages=chat_messages,
        )
        final_reply = chat_res.choices[0].message.content
        log_to_csv(user_input, [], "", False, "", final_reply, status="SUCCESS")
        return final_reply

    except json.JSONDecodeError:
        log_to_csv(user_input, "ERROR", "", False, "", raw_response, status="JSON_ERROR")
        return f"[JSON_ERROR] {raw_response}"


if __name__ == "__main__":
    df = pd.read_csv("pretest.csv")
    df.columns = df.columns.str.strip()

    results = []
    for idx, row in df.iterrows():
        prompt_text = str(row["Prompt ที่ใช้เขียน"]).strip()
        print(f"\n--- ทดสอบข้อที่ {idx + 1}: {prompt_text} ---")
        reply = run_single_prompt(prompt_text)
        print(f"ผลลัพธ์ที่ได้:\n{reply}")
        results.append(reply)

    df["ผลลัพธ์"] = results
    df.to_csv("pretest_result.csv", index=False, encoding="utf-8-sig")
    print("\nบันทึกผลทดสอบทั้งหมดลงไฟล์ pretest_result.csv เรียบร้อยแล้ว")