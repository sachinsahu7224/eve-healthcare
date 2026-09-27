from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.core.database import get_db
from app.models.test import DiagnosticTest
from app.models.user import User
from app.schemas.test import (
    DiagnosticTestCreate,
    DiagnosticTestResponse,
    DiagnosticTestUpdate,
)
from app.utils.exceptions import EntityNotFoundError

router = APIRouter(prefix="/tests", tags=["Diagnostic Tests"])


@router.get(
    "",
    response_model=list[DiagnosticTestResponse],
    summary="List all diagnostic tests",
)
def list_tests(
    is_active: bool | None = Query(None, description="Filter by active status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[DiagnosticTest]:
    """Retrieve diagnostic test catalog with optional active status filter."""
    query = select(DiagnosticTest)
    if is_active is not None:
        query = query.where(DiagnosticTest.is_active == is_active)
    query = query.order_by(DiagnosticTest.name).offset(skip).limit(limit)
    return list(db.scalars(query).all())


@router.post(
    "",
    response_model=DiagnosticTestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new diagnostic test (Admin only)",
)
def create_test(
    request: DiagnosticTestCreate,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_current_admin),
) -> DiagnosticTest:
    """Create a new diagnostic test in the catalog. Requires ADMIN role."""
    test = DiagnosticTest(
        name=request.name,
        description=request.description,
        is_active=request.is_active,
    )
    db.add(test)
    db.commit()
    db.refresh(test)
    return test


@router.get(
    "/{test_id}",
    response_model=DiagnosticTestResponse,
    summary="Get diagnostic test details by ID",
)
def get_test(test_id: int, db: Session = Depends(get_db)) -> DiagnosticTest:
    """Retrieve details for a single diagnostic test."""
    test = db.get(DiagnosticTest, test_id)
    if not test:
        raise EntityNotFoundError("Diagnostic Test", test_id)
    return test


@router.patch(
    "/{test_id}",
    response_model=DiagnosticTestResponse,
    summary="Update or deactivate a diagnostic test (Admin only)",
)
def update_test(
    test_id: int,
    request: DiagnosticTestUpdate,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_current_admin),
) -> DiagnosticTest:
    """Update diagnostic test metadata or deactivate test. Requires ADMIN role."""
    test = db.get(DiagnosticTest, test_id)
    if not test:
        raise EntityNotFoundError("Diagnostic Test", test_id)

    if request.name is not None:
        test.name = request.name
    if request.description is not None:
        test.description = request.description
    if request.is_active is not None:
        test.is_active = request.is_active

    db.commit()
    db.refresh(test)
    return test
