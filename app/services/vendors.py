"""Vendor CRUD service — the add/edit/delete functionality requested
alongside customer CRUD. Kept API-shaped like the other services.
"""
from decimal import Decimal
from sqlalchemy import select

from app.models.vendor import Vendor


def list_vendors(session):
    return session.execute(select(Vendor)).scalars().all()


def create_vendor(session, name, phone, address, pricing_mode, default_rate, branch_id=1):
    if not name or not name.strip():
        raise ValueError("Vendor name is required")
    if pricing_mode not in ("fat_based", "flat_rate"):
        raise ValueError("pricing_mode must be 'fat_based' or 'flat_rate'")
    vendor = Vendor(
        name=name.strip(), phone=phone, address=address,
        pricing_mode=pricing_mode, default_rate=Decimal(default_rate),
        branch_id=branch_id,
    )
    session.add(vendor)
    session.commit()
    return vendor


def update_vendor(session, vendor_id, name=None, phone=None, address=None,
                   pricing_mode=None, default_rate=None):
    vendor = session.get(Vendor, vendor_id)
    if vendor is None:
        raise ValueError(f"No such vendor: {vendor_id}")
    if name is not None:
        if not name.strip():
            raise ValueError("Vendor name is required")
        vendor.name = name.strip()
    if phone is not None:
        vendor.phone = phone
    if address is not None:
        vendor.address = address
    if pricing_mode is not None:
        if pricing_mode not in ("fat_based", "flat_rate"):
            raise ValueError("pricing_mode must be 'fat_based' or 'flat_rate'")
        vendor.pricing_mode = pricing_mode
    if default_rate is not None:
        vendor.default_rate = Decimal(default_rate)
    session.commit()
    return vendor


def delete_vendor(session, vendor_id):
    vendor = session.get(Vendor, vendor_id)
    if vendor is None:
        raise ValueError(f"No such vendor: {vendor_id}")
    if vendor.transactions:
        raise ValueError(
            "Can't delete a vendor with existing delivery history — "
            "this would break the ledger. Consider archiving instead."
        )
    session.delete(vendor)
    session.commit()
