# app/routers/stock.py
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.auth import get_current_user
from app.core.deps import get_db
from app.core.permission_guard import require_permission
from app.models.user import User
from app.models.stock_item import StockItem
from app.models.stock_movement import StockMovement
from app.models.expense import Expense
from app.utils.audit import log_action

from app.schemas.stock import (
    StockItemCreate,
    StockItemUpdate,
    StockItemOut,
    StockMoveCreate,
    StockMovementOut,
    StockSummaryOut,
)

router = APIRouter(prefix="/stock", tags=["stock"])

UNITS = {"un", "kg", "L", "cx"}
INT_UNITS = {"un", "cx"}  # ✅ unidades que só aceitam inteiro
MOVE_TYPES = {"IN", "OUT", "ADJUST"}


def _d(x) -> Decimal:
    if x is None:
        return Decimal("0")
    if isinstance(x, Decimal):
        return x
    return Decimal(str(x))


def _q_money(x: Decimal) -> Decimal:
    return _d(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _q_qty(x: Decimal) -> Decimal:
    # mantém 0.001 para kg/L mas para un/cx a validação impede decimal
    return _d(x).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def _f(x: Decimal | None) -> float | None:
    if x is None:
        return None
    return float(x)


def _iso(dt) -> str | None:
    if not dt:
        return None
    return dt.isoformat()


def _is_int_decimal(x: Decimal) -> bool:
    # True se não tiver parte decimal (ex: 2.000)
    return x == x.to_integral_value()


def _item_out(it: StockItem) -> dict:
    qty = _d(it.qty_on_hand)
    avg = _d(it.avg_unit_cost)
    minq = _d(it.min_qty)
    value = qty * avg

    min_qty = _q_qty(minq)
    qty_on_hand = _q_qty(qty)
    avg_unit_cost = _q_money(avg)
    stock_value = _q_money(value)

    last_purchase = (
        _q_money(_d(it.last_purchase_unit_cost))
        if it.last_purchase_unit_cost is not None
        else None
    )

    return {
        "id": it.id,
        "company_id": it.company_id,
        "name": it.name,
        "sku": it.sku,
        "category": it.category,
        "unit": it.unit,

        "min_qty": _f(min_qty),
        "qty_on_hand": _f(qty_on_hand),
        "avg_unit_cost": _f(avg_unit_cost),
        "last_purchase_unit_cost": _f(last_purchase) if last_purchase is not None else None,

        "supplier_name": it.supplier_name,
        "is_active": bool(it.is_active),

        "needs_restock": bool(qty <= minq),
        "stock_value": _f(stock_value),

        "created_at": _iso(getattr(it, "created_at", None)),
        "updated_at": _iso(getattr(it, "updated_at", None)),
    }


@router.get("", response_model=list[StockItemOut])
@router.get("/", response_model=list[StockItemOut])
def list_stock(
    only_restock: bool = False,
    q: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "stock", "view")

    qry = db.query(StockItem).filter(StockItem.company_id == current_user.company_id)

    if q:
        like = f"%{q.strip()}%"
        qry = qry.filter(
            (StockItem.name.ilike(like)) |
            (StockItem.sku.ilike(like)) |
            (StockItem.category.ilike(like))
        )

    if only_restock:
        qry = qry.filter(StockItem.qty_on_hand <= StockItem.min_qty)

    items = qry.order_by(StockItem.id.desc()).all()
    return [_item_out(it) for it in items]


@router.get("/summary", response_model=StockSummaryOut)
def stock_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "stock", "view")

    total_items = (
        db.query(func.count(StockItem.id))
        .filter(StockItem.company_id == current_user.company_id, StockItem.is_active == True)  # noqa: E712
        .scalar()
        or 0
    )

    needs_restock = (
        db.query(func.count(StockItem.id))
        .filter(
            StockItem.company_id == current_user.company_id,
            StockItem.is_active == True,  # noqa: E712
            StockItem.qty_on_hand <= StockItem.min_qty,
        )
        .scalar()
        or 0
    )

    total_value = (
        db.query(func.coalesce(func.sum(StockItem.qty_on_hand * StockItem.avg_unit_cost), 0))
        .filter(StockItem.company_id == current_user.company_id, StockItem.is_active == True)  # noqa: E712
        .scalar()
        or 0
    )

    return {
        "total_items": int(total_items),
        "needs_restock": int(needs_restock),
        "total_stock_value": float(_q_money(_d(total_value))),
    }


@router.post("", response_model=StockItemOut, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=StockItemOut, status_code=status.HTTP_201_CREATED)
def create_stock_item(
    payload: StockItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "stock", "create")

    unit = (payload.unit or "un").strip()
    if unit not in UNITS:
        raise HTTPException(status_code=400, detail=f"Unidade inválida. Use: {', '.join(sorted(UNITS))}")

    # ✅ min_qty inteiro para un/cx
    min_qty = _d(payload.min_qty)
    if unit in INT_UNITS and not _is_int_decimal(min_qty):
        raise HTTPException(status_code=400, detail="min_qty deve ser inteiro para unidade un/cx")

    it = StockItem(
        company_id=current_user.company_id,
        name=payload.name.strip(),
        sku=(payload.sku.strip() if payload.sku else None),
        category=(payload.category.strip() if payload.category else None),
        unit=unit,
        min_qty=min_qty,
        qty_on_hand=_d(payload.qty_on_hand),
        avg_unit_cost=_d(payload.avg_unit_cost),
        last_purchase_unit_cost=_d(payload.last_purchase_unit_cost) if payload.last_purchase_unit_cost is not None else None,
        supplier_name=(payload.supplier_name.strip() if payload.supplier_name else None),
        is_active=bool(payload.is_active),
    )

    db.add(it)
    db.flush()

    log_action(
        db=db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        action="CREATE",
        entity="stock_items",
        entity_id=it.id,
        old_values=None,
        new_values=_item_out(it),
    )

    db.commit()
    db.refresh(it)
    return _item_out(it)


@router.put("/{item_id}", response_model=StockItemOut)
def update_stock_item(
    item_id: int,
    payload: StockItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "stock", "edit")

    it = (
        db.query(StockItem)
        .filter(StockItem.id == item_id, StockItem.company_id == current_user.company_id)
        .first()
    )
    if not it:
        raise HTTPException(status_code=404, detail="Item de stock não encontrado")

    old = _item_out(it)

    if payload.name is not None:
        it.name = payload.name.strip()
    if payload.sku is not None:
        it.sku = payload.sku.strip() if payload.sku else None
    if payload.category is not None:
        it.category = payload.category.strip() if payload.category else None

    if payload.unit is not None:
        u = payload.unit.strip()
        if u not in UNITS:
            raise HTTPException(status_code=400, detail=f"Unidade inválida. Use: {', '.join(sorted(UNITS))}")
        it.unit = u

    if payload.min_qty is not None:
        min_qty = _d(payload.min_qty)
        if it.unit in INT_UNITS and not _is_int_decimal(min_qty):
            raise HTTPException(status_code=400, detail="min_qty deve ser inteiro para unidade un/cx")
        it.min_qty = min_qty

    if payload.supplier_name is not None:
        it.supplier_name = payload.supplier_name.strip() if payload.supplier_name else None
    if payload.is_active is not None:
        it.is_active = bool(payload.is_active)

    it.updated_at = datetime.utcnow()

    new = _item_out(it)

    log_action(
        db=db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        action="UPDATE",
        entity="stock_items",
        entity_id=it.id,
        old_values=old,
        new_values=new,
    )

    db.commit()
    db.refresh(it)
    return _item_out(it)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_stock_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "stock", "delete")

    it = (
        db.query(StockItem)
        .filter(StockItem.id == item_id, StockItem.company_id == current_user.company_id)
        .first()
    )
    if not it:
        raise HTTPException(status_code=404, detail="Item de stock não encontrado")

    has_moves = (
        db.query(StockMovement.id)
        .filter(
            StockMovement.company_id == current_user.company_id,
            StockMovement.stock_item_id == item_id,
        )
        .first()
    )

    if has_moves:
        raise HTTPException(
            status_code=400,
            detail="Não é possível apagar este artigo porque já tem movimentos de stock associados."
        )

        # Se quiseres em vez disso desativar automaticamente, usa isto:
        # old = _item_out(it)
        # it.is_active = False
        # it.updated_at = datetime.utcnow()
        #
        # log_action(
        #     db=db,
        #     company_id=current_user.company_id,
        #     user_id=current_user.id,
        #     action="UPDATE",
        #     entity="stock_items",
        #     entity_id=it.id,
        #     old_values=old,
        #     new_values=_item_out(it),
        # )
        #
        # db.commit()
        # return None

    old = _item_out(it)
    db.delete(it)

    log_action(
        db=db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        action="DELETE",
        entity="stock_items",
        entity_id=item_id,
        old_values=old,
        new_values=None,
    )

    db.commit()
    return None


@router.get("/{item_id}/moves", response_model=list[StockMovementOut])
def list_item_moves(
    item_id: int,
    limit: int = 200,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "stock", "view")

    it = (
        db.query(StockItem)
        .filter(StockItem.id == item_id, StockItem.company_id == current_user.company_id)
        .first()
    )
    if not it:
        raise HTTPException(status_code=404, detail="Item de stock não encontrado")

    rows = (
        db.query(StockMovement)
        .filter(
            StockMovement.company_id == current_user.company_id,
            StockMovement.stock_item_id == item_id,
        )
        .order_by(StockMovement.id.desc())
        .limit(min(max(limit, 1), 500))
        .all()
    )
    return rows


@router.post("/{item_id}/move", response_model=StockItemOut)
def move_stock(
    item_id: int,
    payload: StockMoveCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "stock", "edit")

    it = (
        db.query(StockItem)
        .filter(StockItem.id == item_id, StockItem.company_id == current_user.company_id)
        .with_for_update()
        .first()
    )
    if not it:
        raise HTTPException(status_code=404, detail="Item de stock não encontrado")

    mtype = (payload.type or "").strip().upper()
    if mtype not in MOVE_TYPES:
        raise HTTPException(status_code=400, detail="Tipo inválido. Use IN | OUT | ADJUST")

    qty = _d(payload.qty)
    if qty <= 0:
        raise HTTPException(status_code=400, detail="Quantidade tem de ser > 0")

    # ✅ qty inteiro para un/cx
    if (it.unit or "").strip() in INT_UNITS and not _is_int_decimal(qty):
        raise HTTPException(status_code=400, detail="Quantidade deve ser inteira para unidade un/cx")

    unit_cost = _d(payload.unit_cost) if payload.unit_cost is not None else None

    old = _item_out(it)

    old_qty = _d(it.qty_on_hand)
    old_avg = _d(it.avg_unit_cost)
    total_cost = None

    if mtype == "IN":
        if unit_cost is None or unit_cost < 0:
            raise HTTPException(status_code=400, detail="unit_cost é obrigatório no IN e tem de ser >= 0")

        new_qty = old_qty + qty

        if new_qty > 0:
            new_avg = ((old_qty * old_avg) + (qty * unit_cost)) / new_qty
        else:
            new_avg = Decimal("0")

        it.qty_on_hand = new_qty
        it.avg_unit_cost = new_avg
        it.last_purchase_unit_cost = unit_cost
        total_cost = qty * unit_cost

    elif mtype == "OUT":
        if qty > old_qty:
            raise HTTPException(status_code=400, detail="Stock insuficiente para essa saída")
        it.qty_on_hand = old_qty - qty

    elif mtype == "ADJUST":
        it.qty_on_hand = qty

    it.updated_at = datetime.utcnow()

    mv = StockMovement(
        company_id=current_user.company_id,
        stock_item_id=it.id,
        user_id=current_user.id,
        type=mtype,
        qty=qty,
        unit_cost=unit_cost,
        total_cost=total_cost,
        reason=(payload.reason.strip() if payload.reason else None),
    )
    db.add(mv)
    db.flush()

    new = _item_out(it)

    log_action(
        db=db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        action="CREATE",
        entity="stock_movement",
        entity_id=mv.id,
        old_values=old,
        new_values={
            "movement": {
                "type": mtype,
                "qty": float(_q_qty(qty)),
                "unit_cost": float(_q_money(unit_cost)) if unit_cost is not None else None,
                "total_cost": float(_q_money(total_cost)) if total_cost is not None else None,
                "reason": payload.reason.strip() if payload.reason else None,
            },
            "item": new,
        },
    )

    db.commit()
    db.refresh(it)
    return _item_out(it)