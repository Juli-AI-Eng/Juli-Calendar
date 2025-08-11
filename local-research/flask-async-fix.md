Querying perplexity using sonar-pro for: Flask server hanging when using asyncio.new_event_loop() and loop.run_until_complete() in threaded mode. What are the best practices for running async code in Flask routes when the server is configured with threaded=True? with maxTokens: 21000
Use Flask’s built‑in async support instead of creating your own event loops in routes. In threaded=True mode, creating a new asyncio loop and calling run_until_complete inside request threads commonly deadlocks or “hangs” because multiple loops compete with Flask’s own per‑request loop management and thread scheduling[5].

Key practices that work reliably:

- Prefer async view functions directly
  - Declare the route async and await coroutines. Flask will start an event loop in a worker thread per request and run the async view on it; you do not need asyncio.new_event_loop(), set_event_loop(), or run_until_complete[5].
  - Example:
    - async def get_data(): ...
    - @app.route("/items")
      async def items(): return await get_data()
- Do not manage the event loop inside a Flask route
  - Avoid loop = asyncio.new_event_loop(); loop.run_until_complete(...). Managing loops per request thread is error‑prone and can hang when mixed with threaded servers, extension middlewares, or other loop users[5].
- If you must call async code from a sync route, use Flask’s ensure_sync
  - current_app.ensure_sync(coro_func)(...) bridges async functions into sync contexts correctly under Flask’s model, rather than manually poking the loop[5].
- Keep blocking work out of async views
  - If you call blocking libraries (DB drivers, SDKs) from an async view, run them in a thread pool (e.g., anyio.to_thread.run_sync or asyncio.to_thread) or switch to non‑blocking drivers. Blocking calls inside the event loop negate async benefits and can appear as hangs under load[5].
- Choose one concurrency model per endpoint
  - Don’t mix “Flask‑managed per‑request event loops” with your own background loop and run_forever threads started from the request handler. If you need a long‑lived loop (e.g., for WebRTC, websockets, schedulers), start it at process startup (before serving) and communicate via thread‑safe queues or asyncio.run_coroutine_threadsafe, not from within request threads[2][4].
- Use production servers that support asyncio patterns appropriately
  - Flask remains WSGI; its async views are executed in a thread with a loop created by Flask. If you need true ASGI semantics, consider moving to an ASGI framework (Quart/FastAPI) and run under uvicorn/hypercorn. If staying with Flask, rely on its documented async behavior rather than overriding the loop policy[5].

Why run_until_complete hangs in threaded=True:

- Each request runs in a thread. Creating a fresh event loop per request and calling run_until_complete can conflict with Flask’s own wrapper that starts an event loop for async views in a thread. Nested or competing loops in the same thread pool lead to deadlocks, especially if extensions or middleware expect sync execution and block the loop[5].
- Starting loop.run_forever in another thread from within a request couples request lifecycle to a background loop. When the request thread dies or the loop’s state changes, further submissions can block, appearing as a hang[2][4].

Safer patterns for special cases:

- Call async code from sync route:
  - result = current_app.ensure_sync(async_fn)(arg1, arg2)[5].
- Submit a coroutine to a long‑lived background loop:
  - Create the loop once at app startup in a dedicated daemon thread; store a reference; use asyncio.run_coroutine_threadsafe(coro, loop) from routes; handle futures carefully and set timeouts[4].
- Offload long tasks:
  - Use a task queue (Celery/RQ) or asyncio background tasks started outside request handlers; return 202 Accepted and poll or use webhooks.

Common pitfalls to avoid:

- Mixing Flask async views with legacy extensions that don’t await; wrap with ensure_sync or upgrade the extension[5].
- Overriding the event loop policy or swapping to uvloop inside Flask without understanding Flask’s wrapper; Flask currently supports only asyncio’s loop model and wraps async views accordingly[5].
- Using examples that create a loop per request and then call run_forever from the request thread; this is a known source of hangs/leaks with frameworks not designed for a single shared loop per process[2].

References:
- Flask’s official async/await documentation: Flask runs an event loop in a thread for async views; use ensure_sync to bridge sync/async and prefer its built‑in model over custom loops[5].
- asyncio event loop docs for safe cross‑thread submission and loop lifecycle considerations[4].
- Community reports show ad‑hoc patterns with new_event_loop + run_until_complete + run_forever in Flask routes; these are fragile and not recommended for general Flask usage[2].