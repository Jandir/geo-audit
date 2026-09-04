## 2025-05-18 - [Python asyncio Pitfall: Coroutines Not Scheduled]
**Learning:** In Python `asyncio`, merely calling an async function like `task_robots = check_robots_txt(url)` returns a coroutine object but does NOT schedule it to run in the background. If you do blocking work or `await` other tasks before `await`ing this coroutine, it will run sequentially, nullifying any intended parallelism.
**Action:** Always wrap background coroutines in `asyncio.create_task()` (or use `asyncio.gather()`) if you want them to run concurrently while other synchronous or asynchronous operations are performed.
## 2025-06-05 - [Python asyncio Pitfall: Concurrency blocked by synchronous CPU tasks]
**Learning:** If you schedule asynchronous I/O-bound background tasks (`asyncio.create_task`) and immediately follow them with synchronous CPU-bound operations before awaiting them, the tasks may never get a chance to start. The CPU operations block the event loop, forcing sequential execution and destroying performance.
**Action:** Always add `await asyncio.sleep(0)` explicitly after scheduling background tasks and before executing synchronous blocking logic. This yields control to the event loop, allowing it to start the async tasks so they can run concurrently with the blocking CPU operations.
## 2025-09-04 - [Lazy Loading Dependencies for Fast CLI Boot]
**Learning:** In a CLI tool like geo-audit.py, eagerly importing large dependencies like google.generativeai and textstat severely degrades startup performance (e.g. from ~0.5s to ~1.5s when just showing help).
**Action:** Use importlib.util.find_spec wrapped in a try/except ModuleNotFoundError block for lightweight availability checking, and move actual import statements to the local scope of functions where they are needed.
