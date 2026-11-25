from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(title="ORACLE CHAT", version="0.1.0")


@app.get("/", response_class=HTMLResponse)
async def home() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORACLE CHAT</title>
</head>
<body>
    <h1>ORACLE CHAT</h1>
    <p>System Online</p>
</body>
</html>"""
