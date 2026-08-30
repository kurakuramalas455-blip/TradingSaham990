import asyncio
from playwright.async_api import async_playwright
import os

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        print("[PROFILER] Connecting to Trading GUI at http://localhost:3000...")
        await page.goto("http://localhost:3000")
        
        # Wait for websocket to connect and start streaming
        await asyncio.sleep(2)
        
        # Setup CDP
        cdp = await page.context.new_cdp_session(page)
        await cdp.send("HeapProfiler.enable")
        
        print("[PROFILER] Taking Heap Snapshot 1 (Baseline)...")
        chunks1 = []
        cdp.on("HeapProfiler.addHeapSnapshotChunk", lambda event: chunks1.append(event["chunk"]))
        await cdp.send("HeapProfiler.takeHeapSnapshot", {"reportProgress": False})
        
        with open("heap_1.heapsnapshot", "w") as f:
            f.write("".join(chunks1))
        
        size1 = os.path.getsize("heap_1.heapsnapshot")
        print(f"[PROFILER] Snapshot 1 Saved ({size1 / 1024 / 1024:.2f} MB)")
        
        print("[PROFILER] Simulating 10 seconds of high-frequency ticks (10,000+ ticks)...")
        await asyncio.sleep(10)
        
        print("[PROFILER] Taking Heap Snapshot 2 (Post-Injection)...")
        chunks2 = []
        cdp.on("HeapProfiler.addHeapSnapshotChunk", lambda event: chunks2.append(event["chunk"]))
        await cdp.send("HeapProfiler.takeHeapSnapshot", {"reportProgress": False})
        
        with open("heap_2.heapsnapshot", "w") as f:
            f.write("".join(chunks2))
            
        size2 = os.path.getsize("heap_2.heapsnapshot")
        print(f"[PROFILER] Snapshot 2 Saved ({size2 / 1024 / 1024:.2f} MB)")
        
        diff = (size2 - size1) / 1024 / 1024
        print(f"[PROFILER] Heap Size Difference: {diff:+.2f} MB")
        if diff < 2.0:
            print("[PROFILER] CONCLUSION: No Detached DOM Elements or significant memory leaks detected.")
        else:
            print("[PROFILER] CONCLUSION: Potential memory leak detected. GC failed to collect.")

        await browser.close()

asyncio.run(main())
