import json

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import torch

from environment import Step, State
from models import StateModel
from neural_network import Network
from utils import create_state_from_model, create_similar_state, evaluate_action_tree


app = FastAPI()
app.mount("/assets", StaticFiles(directory="assets"), name="assets")

model = Network()
model.load_state_dict(torch.load('model.pth'))
model.train(False)


@app.get("/")
async def root():
    return FileResponse('assets/index.html')


async def stream_predict(state: State):
    available = state.get_available_actions()
    if len(available) == 1:
        data = json.dumps({'status': 'finished', 'action': available[0].to_dict()})
        yield f'data: {data}\n\n'
        return
    if len(state.deck) <= 1:
        actions = evaluate_action_tree(model, state)
        action = sorted(actions, key=lambda x: (-x[1], x[0].type.value))[0][0]
    else:
        actions_all = {}
        if len(state.deck) < 6:
            count = 3
        else:
            count = 6
        for i in range(count):
            data = json.dumps({'status': 'processing', 'current_try': i + 1, 'max_try': count})
            yield f'data: {data}\n\n'
            state_copy = create_similar_state(state)
            actions = evaluate_action_tree(model, state_copy)
            for action, score in actions:
                if action in actions_all:
                    actions_all[action] += score
                else:
                    actions_all[action] = score
        for k in actions_all.keys():
            actions_all[k] = actions_all[k] / count
        actions_all = [(k, v) for k, v in actions_all.items()]
        action = sorted(actions_all, key=lambda x: (-x[1], x[0].type.value))[0][0]
    data = json.dumps({'status': 'finished', 'action': action.to_dict()})
    yield f'data: {data}\n\n'


@app.post('/predict')
async def predict(state_model: StateModel = None):
    try:
        state = create_state_from_model(state_model)
    except:
        return PlainTextResponse('Error while parsing state', status_code=400)
    if state.step in (Step.OPPONENT_ATTACK, Step.OPPONENT_DEFEND):
        return PlainTextResponse('Opponent turn is not allowed', status_code=400)
    if state.finished:
        return PlainTextResponse('State is finished', status_code=400)
    return StreamingResponse(stream_predict(state), media_type="text/event-stream")


if __name__ == '__main__':
    uvicorn.run(app, port=8003)
