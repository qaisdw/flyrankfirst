import os
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

def main():
    print("Connecting to Gemini...")
    
    # Read configuration safely from environment variables
    client = OpenAI(
        base_url=os.getenv("LLM_BASE_URL"),
        api_key=os.getenv("LLM_API_KEY"),
    )

    try:
        response = client.chat.completions.create(
            model=os.getenv("LLM_MODEL"),
            messages=[
                {"role": "user", "content": "Reply with exactly the word: ready"}
            ],
        )
        print("Success! Response:")
        print(response.choices[0].message.content.strip())
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()