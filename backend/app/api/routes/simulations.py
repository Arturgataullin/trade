from fastapi import APIRouter, HTTPException, status

from backend.app.api.dependencies import CurrentUser, DbSession
from backend.app.schemas.simulation import SimulationRead, SimulationWrite
from backend.app.services.simulations import (
    InvalidSimulationConfigurationError,
    SimulationNotFoundError,
    create_simulation,
    get_simulation,
    list_simulations,
    update_simulation,
)


router = APIRouter(prefix="/simulations", tags=["simulations"])


@router.post(
    "",
    response_model=SimulationRead,
    status_code=status.HTTP_201_CREATED,
)
def add_simulation(
    data: SimulationWrite,
    db: DbSession,
    current_user: CurrentUser,
) -> SimulationRead:
    try:
        simulation = create_simulation(db, current_user.id, data)
    except InvalidSimulationConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return SimulationRead.model_validate(simulation)


@router.get("", response_model=list[SimulationRead])
def read_simulations(
    db: DbSession,
    current_user: CurrentUser,
) -> list[SimulationRead]:
    return [
        SimulationRead.model_validate(simulation)
        for simulation in list_simulations(db, current_user.id)
    ]


@router.get("/{simulation_id}", response_model=SimulationRead)
def read_simulation(
    simulation_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> SimulationRead:
    try:
        simulation = get_simulation(db, simulation_id, current_user.id)
    except SimulationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Experiment not found",
        ) from exc
    return SimulationRead.model_validate(simulation)


@router.put("/{simulation_id}", response_model=SimulationRead)
def edit_simulation(
    simulation_id: int,
    data: SimulationWrite,
    db: DbSession,
    current_user: CurrentUser,
) -> SimulationRead:
    try:
        simulation = update_simulation(
            db,
            simulation_id,
            current_user.id,
            data,
        )
    except SimulationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Experiment not found",
        ) from exc
    except InvalidSimulationConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return SimulationRead.model_validate(simulation)
