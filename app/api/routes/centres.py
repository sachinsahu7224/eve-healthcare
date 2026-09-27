from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_admin
from app.core.database import get_db
from app.models.centre import DiagnosticCentre
from app.models.centre_test import CentreTest
from app.models.test import DiagnosticTest
from app.models.user import User
from app.schemas.centre import (
    CentreTestAssignRequest,
    CentreTestAssignResponse,
    DiagnosticCentreCreate,
    DiagnosticCentreDetailResponse,
    DiagnosticCentreResponse,
    DiagnosticCentreUpdate,
)
from app.schemas.test import DiagnosticTestWithPrice
from app.utils.exceptions import EntityNotFoundError

router = APIRouter(prefix="/centres", tags=["Diagnostic Centres"])


@router.get(
    "",
    response_model=list[DiagnosticCentreResponse],
    summary="List all diagnostic centres",
)
def list_centres(
    is_active: bool | None = Query(None, description="Filter by active status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[DiagnosticCentre]:
    """Retrieve diagnostic centres with optional active status filtering."""
    query = select(DiagnosticCentre)
    if is_active is not None:
        query = query.where(DiagnosticCentre.is_active == is_active)
    query = query.order_by(DiagnosticCentre.name).offset(skip).limit(limit)
    return list(db.scalars(query).all())


@router.post(
    "",
    response_model=DiagnosticCentreResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new diagnostic centre (Admin only)",
)
def create_centre(
    request: DiagnosticCentreCreate,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_current_admin),
) -> DiagnosticCentre:
    """Create a new diagnostic centre facility. Requires ADMIN privileges."""
    centre = DiagnosticCentre(
        name=request.name,
        location=request.location,
        is_active=request.is_active,
    )
    db.add(centre)
    db.commit()
    db.refresh(centre)
    return centre


@router.get(
    "/{centre_id}",
    response_model=DiagnosticCentreDetailResponse,
    summary="Get centre details with available tests and prices",
)
def get_centre(
    centre_id: int,
    db: Session = Depends(get_db),
) -> DiagnosticCentreDetailResponse:
    """Fetch details of a single diagnostic centre including its offering tests and prices."""
    stmt = (
        select(DiagnosticCentre)
        .options(joinedload(DiagnosticCentre.centre_tests).joinedload(CentreTest.test))
        .where(DiagnosticCentre.id == centre_id)
    )
    centre = db.scalar(stmt)
    if not centre:
        raise EntityNotFoundError("Diagnostic Centre", centre_id)

    # Format available tests with their specific centre prices
    tests_with_prices = [
        DiagnosticTestWithPrice(
            id=ct.test.id,
            name=ct.test.name,
            description=ct.test.description,
            is_active=ct.test.is_active,
            price=ct.price,
        )
        for ct in centre.centre_tests
        if ct.test is not None and ct.test.is_active
    ]

    return DiagnosticCentreDetailResponse(
        id=centre.id,
        name=centre.name,
        location=centre.location,
        is_active=centre.is_active,
        tests=tests_with_prices,
        created_at=centre.created_at,
        updated_at=centre.updated_at,
    )


@router.patch(
    "/{centre_id}",
    response_model=DiagnosticCentreResponse,
    summary="Update or deactivate a diagnostic centre (Admin only)",
)
def update_centre(
    centre_id: int,
    request: DiagnosticCentreUpdate,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_current_admin),
) -> DiagnosticCentre:
    """Update centre details or set is_active=False to deactivate. Requires ADMIN role."""
    centre = db.get(DiagnosticCentre, centre_id)
    if not centre:
        raise EntityNotFoundError("Diagnostic Centre", centre_id)

    if request.name is not None:
        centre.name = request.name
    if request.location is not None:
        centre.location = request.location
    if request.is_active is not None:
        centre.is_active = request.is_active

    db.commit()
    db.refresh(centre)
    return centre


@router.post(
    "/{centre_id}/tests",
    response_model=CentreTestAssignResponse,
    summary="Assign or update a test price at a centre (Admin only)",
)
def assign_test_to_centre(
    centre_id: int,
    request: CentreTestAssignRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_current_admin),
) -> CentreTestAssignResponse:
    """Associate a diagnostic test with a centre and set its price. Requires ADMIN role."""
    centre = db.get(DiagnosticCentre, centre_id)
    if not centre:
        raise EntityNotFoundError("Diagnostic Centre", centre_id)

    test = db.get(DiagnosticTest, request.test_id)
    if not test:
        raise EntityNotFoundError("Diagnostic Test", request.test_id)

    centre_test = db.scalar(
        select(CentreTest).where(
            CentreTest.centre_id == centre_id,
            CentreTest.test_id == request.test_id,
        )
    )

    if centre_test:
        centre_test.price = request.price
    else:
        centre_test = CentreTest(
            centre_id=centre_id,
            test_id=request.test_id,
            price=request.price,
        )
        db.add(centre_test)

    db.commit()
    return CentreTestAssignResponse(
        centre_id=centre_id,
        test_id=request.test_id,
        price=request.price,
    )


@router.delete(
    "/{centre_id}/tests/{test_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a test offering from a centre (Admin only)",
)
def remove_test_from_centre(
    centre_id: int,
    test_id: int,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_current_admin),
) -> None:
    """Disassociate a diagnostic test from a centre. Requires ADMIN role."""
    centre_test = db.scalar(
        select(CentreTest).where(
            CentreTest.centre_id == centre_id,
            CentreTest.test_id == test_id,
        )
    )
    if not centre_test:
        raise EntityNotFoundError("Centre Test Offering", f"centre:{centre_id}, test:{test_id}")

    db.delete(centre_test)
    db.commit()
