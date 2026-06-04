import os
from dotenv import load_dotenv
from openai import OpenAI

def run_test():
    load_dotenv(override=True)

    print("MINIMAX_API_KEY =", os.getenv("MINIMAX_KEY"))
    print("OPENAI_BASE_URL =", os.getenv("OPENAI_BASE_URL"))
    print("OPENAI_API_KEY =", os.getenv("OPENAI_API_KEY"))

    # 🟡 Assure-toi qu'OPENAI_API_KEY et OPENAI_BASE_URL sont bien dans l’environnement
    client = OpenAI()

    try:
        resp = client.chat.completions.create(
            model="MiniMax-M3",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Test message"}
            ],
            max_tokens=200,
            user="test_connection_user"
        )
        
        message = resp.choices[0].message
        # Safely verify if model refused request before accessing content (CWE-252)
        if hasattr(message, "refusal") and message.refusal:
             print("Request Refused by Model:", message.refusal)
        else:
             import sys
             content = message.content or ""
             safe_content = content.encode(sys.stdout.encoding or 'utf-8', errors='replace').decode(sys.stdout.encoding or 'utf-8')
             print(safe_content)
    except Exception as e:
        print("API Call failed:", str(e))

if __name__ == "__main__":
    run_test()
