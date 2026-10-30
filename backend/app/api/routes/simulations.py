from fastapi import APIRouter, HTTPException, Query, status

from backend.app.api.dependencies import CurrentUser, DbSession
from backend.app.schemas.simulation import SimulationRead, SimulationWrite
from backend.app.schemas.simulation_run import SimulationRunRead
from backend.app.services.simulation_runs import (
    SimulationAlreadyRunningError,
    SimulationCannotStartError,
    SimulationNotRunningError,
    get_latest_run,
    start_simulation,
    stop_simulation,
)
from backend.app.services.simulations import (
    InvalidSimulationConfigurationError,
    SimulationNotFoundError,
    SimulationRunningError,
    create_simulation,
    get_simulation,
    list_simulations,
    update_simulation,
)


router = APIRouter(prefix="/simulations", tags=["simulations"])


@router.post(
    "/{simulation_id}/start",
    response_model=SimulationRunRead,
    status_code=status.HTTP_201_CREATED,
)
def start_simulation_run(
    simulation_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> SimulationRunRead:
    try:
        run = start_simulation(db, simulation_id, current_user.id)
    except SimulationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Experiment not found",
        ) from exc
    except SimulationAlreadyRunningError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Experiment is already running",
        ) from exc
    except SimulationCannotStartError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return SimulationRunRead.model_validate(run)


@router.post(
    "/{simulation_id}/stop",
    response_model=SimulationRunRead,
)
def stop_simulation_run(
    simulation_id: int,
    db: DbSession,
    current_user: CurrentUser,
    run_id: int | None = Query(default=None, gt=0),
) -> SimulationRunRead:
    try:
        run = stop_simulation(db, simulation_id, current_user.id, expected_run_id=run_id)
    except SimulationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Experiment not found",
        ) from exc
    except SimulationNotRunningError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Experiment is not running",
        ) from exc
    return SimulationRunRead.model_validate(run)


@router.get(
    "/{simulation_id}/run",
    response_model=SimulationRunRead | None,
)
def read_latest_simulation_run(
    simulation_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> SimulationRunRead | None:
    try:
        get_simulation(db, simulation_id, current_user.id)
    except SimulationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Experiment not found",
        ) from exc
    run = get_latest_run(db, simulation_id, current_user.id)
    return SimulationRunRead.model_validate(run) if run is not None else None


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
    except SimulationRunningError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A running experiment cannot be edited",
        ) from exc
    return SimulationRead.model_validate(simulation)
