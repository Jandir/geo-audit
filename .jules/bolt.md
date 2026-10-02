## 2025-05-18 - [Python asyncio Pitfall: Coroutines Not Scheduled]
**Learning:** In Python `asyncio`, merely calling an async function like `task_robots = check_robots_txt(url)` returns a coroutine object but does NOT schedule it to run in the background. If you do blocking work or `await` other tasks before `await`ing this coroutine, it will run sequentially, nullifying any intended parallelism.
**Action:** Always wrap background coroutines in `asyncio.create_task()` (or use `asyncio.gather()`) if you want them to run concurrently while other synchronous or asynchronous operations are performed.
## 2025-06-05 - [Python asyncio Pitfall: Concurrency blocked by synchronous CPU tasks]
**Learning:** If you schedule asynchronous I/O-bound background tasks (`asyncio.create_task`) and immediately follow them with synchronous CPU-bound operations before awaiting them, the tasks may never get a chance to start. The CPU operations block the event loop, forcing sequential execution and destroying performance.
**Action:** Always add `await asyncio.sleep(0)` explicitly after scheduling background tasks and before executing synchronous blocking logic. This yields control to the event loop, allowing it to start the async tasks so they can run concurrently with the blocking CPU operations.

## 2024-05-18 - Lazy Loading Heavy ML/Analytics Imports
**Learning:** Initializing heavy libraries (like `google.generativeai` and `textstat`) globally at the top of a Python CLI script can drastically slow down the startup time (e.g., from ~0.2s to >1.5s), even for simple commands like `--help` where these libraries are not used. Using `importlib.util.find_spec` in a `try...except ModuleNotFoundError` block is an efficient way to check for a module's presence without executing its top-level code.
**Action:** Always lazy-load heavy machine learning or analytics libraries inside the specific functions where they are needed for CLI applications to ensure lightning-fast startup times.
