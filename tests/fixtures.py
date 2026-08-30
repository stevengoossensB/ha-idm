"""Portal payloads captured from a real Mijn IDM account.

Values are verbatim from the portal (so the decimal-string formats, the mixed
timestamp shapes and the field names are exactly what the client must cope
with); the street, house number, barcodes and national registration number have
been replaced with placeholders.
"""

from __future__ import annotations

USER = {
    "email": "resident@example.be",
    "first_name": "Resident",
    "last_name": "Example",
}

SCOPE = {
    "view_address": True,
    "view_emptyings": True,
    "view_dumpings": True,
    "view_waste_on_demands": True,
    "view_recycling_center_visits": True,
    "view_yearly_cost": True,
    "view_residual_waste_consumption_comparison": True,
}

ADDRESS = {
    "id": "8c4c9bb5-741b-4fa2-8680-f520cb5c513e",
    "category": "private",
    "city": "Lokeren",
    "street": "Stationstraat",
    "house_number": "1",
    "zipcode": 9160,
    "national_registration_number": "60010112345",
    "company_name": None,
    "recycling_center_badge": None,
}

# Same physical address, but a session later: the portal has issued a new UUID.
ADDRESS_ROTATED_UUID = {**ADDRESS, "id": "9e1ba232-a923-44f0-8fab-dd1eab9bbace"}

LEDIGINGEN = {
    "availableFractions": ["REST", "GFT"],
    "fractions": ["REST", "GFT"],
    "fromDate": "01/01/2010",
    "untilDate": "30/08/2026",
    "totalWeight": 3865,
    "totalPrice": 813.9400000000005,
    "emptyings": [
        {
            "emptying_id": 15807405,
            "barcode": "0000000001",
            "fraction": "REST",
            "volume": "240",
            "price": "3.30",
            "service_cost": "0.50",
            "unit_cost": "0.20",
            "weight": "14.00",
            "emptied_on": "2026-07-31T11:25:00.000000Z",
        },
        {
            "emptying_id": 15790112,
            "barcode": "0000000002",
            "fraction": "GFT",
            "volume": "120",
            "price": "1.42",
            "service_cost": "0.50",
            "unit_cost": "0.12",
            "weight": "7.67",
            "emptied_on": "2026-07-24T09:02:00.000000Z",
        },
        {
            "emptying_id": 15701003,
            "barcode": "0000000001",
            "fraction": "REST",
            "volume": "240",
            "price": "2.90",
            "service_cost": "0.50",
            "unit_cost": "0.20",
            "weight": "12.00",
            "emptied_on": "2026-07-17T11:31:00.000000Z",
        },
    ],
}

OVERZICHT = {
    "yearlyCostSummary": {
        "years": [2025, 2026],
        "series": [
            {"name": "REST", "data": ["147.10", "60.40"]},
            {"name": "GFT", "data": ["3.18", "14.16"]},
        ],
    },
    "occupantCount": 5,
    "residualWasteConsumptions": [
        {"year": 2022, "total_weight": 893.5},
        {"year": 2023, "total_weight": 945},
        {"year": 2024, "total_weight": 919.5},
        {"year": 2025, "total_weight": 678},
        {"year": 2026, "total_weight": 284.5},
    ],
    "averageResidualWasteConsumptions": [
        {"year": 2026, "occupant_count": 1, "average_weight": 180.10},
        {"year": 2026, "occupant_count": 4, "average_weight": 495.00},
        {"year": 2026, "occupant_count": 5, "average_weight": 569.00},
    ],
    "recyclingCenterVisits": [
        {
            "id": 20059742,
            "date": "2026-08-29T00:00:00.000000Z",
            "locationName": "Lokeren",
            "price": "0.00",
            "weight": "25.00",
            "details": [
                {
                    "id": 20087015,
                    "fraction": "Recycleerbaar",
                    "unitPrice": "0.00",
                    "weight": "25.00",
                    "price": "0.00",
                }
            ],
        },
        {
            "id": 20011111,
            "date": "2026-06-02T00:00:00.000000Z",
            "locationName": "Lokeren",
            "price": "0.00",
            "weight": "40.00",
            "details": [],
        },
    ],
}

RECYCLAGEPARKEN = {
    "year": 2026,
    "recyclingCenter": "all",
    "limit": 5,
    "plannedReservations": [
        {
            "id": 571999,
            # A bare date, unlike the visits above -- must still become an
            # aware datetime for a timestamp sensor.
            "date": "2026-09-12",
            "opens_at": "14:45",
            "closes_at": "15:00",
            "recycling_center": {
                "id": 4,
                "name": "Lokeren - Bobijnerslaan",
                "address": "Bobijnerslaan",
            },
            "can_be_cancelled": True,
        }
    ],
    "pastReservations": [
        {
            "id": 571920,
            "date": "2025-02-08",
            "opens_at": "14:45",
            "closes_at": "15:00",
            "recycling_center": {
                "id": 4,
                "name": "Lokeren - Bobijnerslaan",
                "address": "Bobijnerslaan",
            },
            "can_be_cancelled": False,
        }
    ],
    "wasteDistribution": {
        "data": [
            {
                "fraction": "Recycleerbaar",
                "free": True,
                "unit": "kg",
                "weight": 265,
                "full_weight": 265,
                "price": "0.00",
                "color": "#e45a76",
            },
            {
                "fraction": "Niet-Recycleerbaar",
                "free": False,
                "unit": "kg",
                "weight": 60,
                "full_weight": 60,
                "price": "12.00",
                "color": "#f8955b",
            },
        ]
    },
}

STORTINGEN = {
    "dumpings": [],
    "fromDate": "01/01/2010",
    "untilDate": "30/08/2026",
    "totalPrice": 0,
}

AFVAL_OP_AFROEP = {
    "wasteOnDemands": [],
    "fromDate": "01/01/2010",
    "untilDate": "30/08/2026",
    "totalPrice": 0,
    "totalWeight": 0,
}
