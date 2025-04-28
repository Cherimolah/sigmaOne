from gino import Gino
from sqlalchemy import Column, Integer, Boolean, Float, LargeBinary

from config import PG_USER, PG_PASSWORD, DB_NAME


class Database(Gino):

    def __init__(self):
        super().__init__()

        class Step(self.Model):
            __tablename__ = 'steps'

            id = Column(Integer, primary_key=True)
            state = Column(LargeBinary, nullable=False)
            next_state = Column(LargeBinary, nullable=True)
            done = Column(Boolean, nullable=False)
            reward = Column(Float, nullable=False)
            action_id = Column(Integer, nullable=True)

        self.Step = Step

        class Step2(self.Model):
            __tablename__ = 'steps2'

            id = Column(Integer, primary_key=True)
            state = Column(LargeBinary, nullable=False)
            action_id = Column(Integer, nullable=True)

        self.Step2 = Step2

    async def connect(self):
        await self.set_bind(f'postgresql://{PG_USER}:{PG_PASSWORD}@localhost:5432/{DB_NAME}')
        await self.gino.create_all()


db = Database()
