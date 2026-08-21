## 2025-05-18 - [Python asyncio Pitfall: Coroutines Not Scheduled]
**Learning:** In Python `asyncio`, merely calling an async function like `task_robots = check_robots_txt(url)` returns a coroutine object but does NOT schedule it to run in the background. If you do blocking work or `await` other tasks before `await`ing this coroutine, it will run sequentially, nullifying any intended parallelism.
**Action:** Always wrap background coroutines in `asyncio.create_task()` (or use `asyncio.gather()`) if you want them to run concurrently while other synchronous or asynchronous operations are performed.
## 2025-06-05 - [Python asyncio Pitfall: Concurrency blocked by synchronous CPU tasks]
**Learning:** If you schedule asynchronous I/O-bound background tasks (`asyncio.create_task`) and immediately follow them with synchronous CPU-bound operations before awaiting them, the tasks may never get a chance to start. The CPU operations block the event loop, forcing sequential execution and destroying performance.
**Action:** Always add `await asyncio.sleep(0)` explicitly after scheduling background tasks and before executing synchronous blocking logic. This yields control to the event loop, allowing it to start the async tasks so they can run concurrently with the blocking CPU operations.
## 2026-08-21 - Lazy-loading Heavy ML Dependencies in CLI
**Learning:** Loading heavy libraries like `textstat` and `google.generativeai` in the global scope significantly blocks the startup time of Python CLI tools (e.g. from 0.5s to ~2s).
**Action:** Use `importlib.util.find_spec` for availability checks in the global scope and lazy-load the actual modules inside their respective functions to preserve fast CLI startup.
