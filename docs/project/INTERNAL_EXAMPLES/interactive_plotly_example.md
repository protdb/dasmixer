# Пример интерактивного отображения Plotly с помощью pywebiew

```python
import flet
import multiprocessing
import webview
import plotly.express as px
import plotly.graph_objects as go

def show_vw(plot: go.Figure):
    html = plot.to_html(include_plotlyjs='cdn')
    window = webview.create_window('Multiprocess State Example', html=html)
    webview.start()

def main(page: flet.Page):

    def launch_vw(plot: go.Figure):
        webview_process = multiprocessing.Process(target=show_vw, args=(plot,))
        webview_process.start()
        webview_process.join()

    df = px.data.tips()
    fig = px.box(df, x="time", y="total_bill")
    img = fig.to_image(width=1000, height=500)

    def btn_click(e):
        launch_vw(fig)

    page.add(flet.Image(src=img))
    btn = flet.Button(flet.Text("Press to open interactively"), on_click=btn_click)
    page.add(btn)

if __name__ == '__main__':
    flet.app(target=main)
    # show_vw(px.box(px.data.tips(), x="time", y="total_bill"))
```

## Дополнительный пример: asyncio и multiprocessing

```python
import asyncio
from concurrent.futures import ProcessPoolExecutor
import time
import os

# This function will run in a separate process
# It must be a top-level function so it can be pickled and run in a new process
def cpu_heavy_task(duration):
    """A CPU-bound task that blocks for a duration."""
    print(f"Process {os.getpid()}: Starting CPU-heavy task for {duration} seconds...")
    start_time = time.time()
    while time.time() - start_time < duration:
        # Simulate heavy computation
        pass
    print(f"Process {os.getpid()}: Finished CPU-heavy task.")
    return f"Task completed in {duration}s"

async def main():
    print("Main process: Starting async operations.")
    # Create a ProcessPoolExecutor
    executor = ProcessPoolExecutor(max_workers=3)
    loop = asyncio.get_running_loop()

    # Schedule the CPU-heavy tasks to run in the executor
    tasks = [
        loop.run_in_executor(executor, cpu_heavy_task, 2),
        loop.run_in_executor(executor, cpu_heavy_task, 3),
        loop.run_in_executor(executor, cpu_heavy_task, 1),
    ]

    # Await all tasks concurrently
    results = await asyncio.gather(*tasks)
    print(f"Main process: All tasks finished. Results: {results}")

if __name__ == "__main__":
    # This guard is necessary for multiprocessing to work correctly
    asyncio.run(main())

```