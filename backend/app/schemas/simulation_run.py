from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


RunStatus = Literal["running", "stopped", "completed", "failed"]


class SimulationRunRead(BaseModel):
    id: int
    simulation_id: int
    status: RunStatus
    current_step: int
    total_steps: int
    seed: int
    engine_version: str
    stop_requested: bool
    started_at: datetime
    finished_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
