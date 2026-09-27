from decimal import Decimal

from fastapi.testclient import TestClient

from app.models.centre import DiagnosticCentre
from app.models.centre_test import CentreTest
from app.models.test import DiagnosticTest


def test_list_centres(client: TestClient, sample_centre: DiagnosticCentre):
    response = client.get("/api/v1/centres")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["name"] == sample_centre.name


def test_get_centre_details_with_tests(
    client: TestClient,
    sample_centre: DiagnosticCentre,
    sample_test: DiagnosticTest,
    sample_offering: CentreTest,
):
    response = client.get(f"/api/v1/centres/{sample_centre.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == sample_centre.id
    assert len(data["tests"]) == 1
    assert data["tests"][0]["name"] == sample_test.name
    assert Decimal(str(data["tests"][0]["price"])) == sample_offering.price


def test_admin_create_centre_success(client: TestClient, admin_headers: dict):
    response = client.post(
        "/api/v1/centres",
        headers=admin_headers,
        json={
            "name": "Koramangala Diagnostic Care",
            "location": "Koramangala, Bangalore",
            "is_active": True,
        },
    )
    assert response.status_code == 201
    assert response.json()["name"] == "Koramangala Diagnostic Care"


def test_patient_create_centre_forbidden(client: TestClient, patient_headers: dict):
    response = client.post(
        "/api/v1/centres",
        headers=patient_headers,
        json={"name": "Unauthorized Centre", "location": "Anywhere", "is_active": True},
    )
    assert response.status_code == 403
    assert "Administrator access required" in response.json()["detail"]


def test_admin_create_test_success(client: TestClient, admin_headers: dict):
    response = client.post(
        "/api/v1/tests",
        headers=admin_headers,
        json={
            "name": "Thyroid Stimulating Hormone (TSH)",
            "description": "Measures TSH levels",
        },
    )
    assert response.status_code == 201
    assert response.json()["name"] == "Thyroid Stimulating Hormone (TSH)"


def test_patient_create_test_forbidden(client: TestClient, patient_headers: dict):
    response = client.post(
        "/api/v1/tests",
        headers=patient_headers,
        json={"name": "Unauthorized Test"},
    )
    assert response.status_code == 403


def test_admin_assign_test_price(
    client: TestClient,
    admin_headers: dict,
    sample_centre: DiagnosticCentre,
    sample_test: DiagnosticTest,
):
    response = client.post(
        f"/api/v1/centres/{sample_centre.id}/tests",
        headers=admin_headers,
        json={"test_id": sample_test.id, "price": "650.00"},
    )
    assert response.status_code == 200
    assert Decimal(str(response.json()["price"])) == Decimal("650.00")

    # Verify reflected in centre detail
    detail_res = client.get(f"/api/v1/centres/{sample_centre.id}")
    assert Decimal(str(detail_res.json()["tests"][0]["price"])) == Decimal("650.00")


def test_admin_deactivate_centre(client: TestClient, admin_headers: dict, sample_centre: DiagnosticCentre):
    response = client.patch(
        f"/api/v1/centres/{sample_centre.id}",
        headers=admin_headers,
        json={"is_active": False},
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False
