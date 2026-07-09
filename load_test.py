import asyncio
import aiohttp
import time

URL = "https://your-app.onrender.com/chat"   # Change to your Render URL

async def send_message(session, user_id):
    payload = {"message": "Hi", "email": f"test{user_id}@example.com"}
    start = time.time()
    try:
        async with session.post(URL, json=payload) as resp:
            data = await resp.json()
            elapsed = (time.time() - start) * 1000
            print(f"User {user_id}: {data.get('reply', '')[:40]}... ({elapsed:.0f}ms)")
    except Exception as e:
        print(f"User {user_id} failed: {e}")

async def main():
    num_users = 10   # Start with 10; increase to 50, 100, etc.
    async with aiohttp.ClientSession() as session:
        tasks = [send_message(session, i) for i in range(num_users)]
        await asyncio.gather(*tasks)
        print(f"\n✅ {num_users} requests completed.")

if __name__ == "__main__":
    asyncio.run(main())
