from fastapi import FastAPI
from fastapi.responses import FileResponse
from starlette.staticfiles import StaticFiles
import uvicorn
from pydantic import BaseModel

from environment import Environment


app = FastAPI()
app.mount("/assets", StaticFiles(directory="assets"))


class GameParams(BaseModel):
    deck_size: int
    transferable: bool


@app.get("/")
async def root():
    return FileResponse("index1.html")


@app.post("/create_game")
async def create_game(game_params: GameParams):
    env = Environment(game_params.deck_size, game_params.transferable)
    env.reset()
    return env.state


if __name__ == '__main__':
    uvicorn.run(app)
