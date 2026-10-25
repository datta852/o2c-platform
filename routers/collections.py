from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import (
    get_db, InvoiceDB, PaymentAllocationDB, DunningRuleDB, CollectionActionDB,
)
from schemas import (
    CollectionActionOutcome, CollectionActionResponse, CollectionActionStatus,
    DunningRuleCreate, DunningRuleResponse, DunningRuleUpdate,
    ReceivableResponse, ReceivablesSummary,
)
from security import require_api_key

router = APIRouter(prefix="/collections", tags=["Collections"], dependencies=[Depends(require_api_key)])
receivables_router = APIRouter(prefix="/receivables", tags=["Receivables"], dependencies=[Depends(require_api_key)])


def _receivables_query(db: Session):
    return (
        db.query(
            InvoiceDB,
            func.coalesce(func.sum(PaymentAllocationDB.allocated_amount), 0).label("allocated"),
        )
        .outerjoin(PaymentAllocationDB, PaymentAllocationDB.invoice_id == InvoiceDB.invoice_id)
        .filter(InvoiceDB.invoice_status != "CANCELLED")
        .group_by(InvoiceDB.invoice_id)
    )


def _to_receivable(invoice: InvoiceDB, allocated, as_of: date) -> ReceivableResponse:
    allocated = allocated or 0
    outstanding = invoice.invoice_amount - allocated
    return ReceivableResponse(
        invoice_id=invoice.invoice_id,
        invoice_number=invoice.invoice_number,
        customer_id=invoice.customer_id,
        due_date=invoice.due_date,
        invoice_amount=invoice.invoice_amount,
        allocated_amount=allocated,
        outstanding_amount=outstanding,
        days_overdue=max((as_of - invoice.due_date).days, 0),
    )


@receivables_router.get("/", response_model=list[ReceivableResponse])
def list_receivables(
    customer_id: int | None = Query(default=None, gt=0),
    overdue_only: bool = False,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    as_of: date | None = None,
    db: Session = Depends(get_db),
):
    as_of = as_of or date.today()
    query = _receivables_query(db)
    if customer_id is not None:
        query = query.filter(InvoiceDB.customer_id == customer_id)
    if overdue_only:
        query = query.filter(InvoiceDB.due_date < as_of)
    rows = query.order_by(InvoiceDB.due_date, InvoiceDB.invoice_id).offset(offset).limit(limit).all()
    return [
        _to_receivable(invoice, allocated, as_of)
        for invoice, allocated in rows
        if invoice.invoice_amount > allocated
    ]


@receivables_router.get("/summary", response_model=ReceivablesSummary)
def receivables_summary(as_of: date | None = None, db: Session = Depends(get_db)):
    as_of = as_of or date.today()
    rows = _receivables_query(db).all()
    outstanding = [
        (invoice, invoice.invoice_amount - (allocated or 0))
        for invoice, allocated in rows
        if invoice.invoice_amount > (allocated or 0)
    ]
    overdue = [(invoice, amount) for invoice, amount in outstanding if invoice.due_date < as_of]
    return ReceivablesSummary(
        outstanding_amount=sum((amount for _, amount in outstanding), start=0),
        overdue_amount=sum((amount for _, amount in overdue), start=0),
        outstanding_invoice_count=len(outstanding),
        overdue_invoice_count=len(overdue),
    )


@router.post("/rules", response_model=DunningRuleResponse, status_code=201)
def create_dunning_rule(rule: DunningRuleCreate, db: Session = Depends(get_db)):
    db_rule = DunningRuleDB(**rule.model_dump())
    db.add(db_rule)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="A dunning rule with this name already exists") from error
    db.refresh(db_rule)
    return db_rule


@router.get("/rules", response_model=list[DunningRuleResponse])
def list_dunning_rules(db: Session = Depends(get_db)):
    return db.query(DunningRuleDB).order_by(DunningRuleDB.days_overdue, DunningRuleDB.rule_id).all()


@router.put("/rules/{rule_id}", response_model=DunningRuleResponse)
def update_dunning_rule(rule_id: int, rule: DunningRuleUpdate, db: Session = Depends(get_db)):
    db_rule = db.query(DunningRuleDB).filter(DunningRuleDB.rule_id == rule_id).first()
    if not db_rule:
        raise HTTPException(status_code=404, detail="Dunning rule not found")
    for field, value in rule.model_dump().items():
        setattr(db_rule, field, value)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="A dunning rule with this name already exists") from error
    db.refresh(db_rule)
    return db_rule


@router.post("/run", response_model=list[CollectionActionResponse])
def run_collections(as_of: date | None = None, db: Session = Depends(get_db)):
    """Schedule due collection actions without sending external messages."""
    as_of = as_of or date.today()
    rules = db.query(DunningRuleDB).filter(DunningRuleDB.enabled.is_(True)).all()
    invoices = _receivables_query(db).filter(InvoiceDB.due_date < as_of).all()
    existing_pairs = {
        (invoice_id, rule_id)
        for invoice_id, rule_id in db.query(
            CollectionActionDB.invoice_id, CollectionActionDB.rule_id
        ).all()
    }

    created = []
    for invoice, allocated in invoices:
        outstanding = invoice.invoice_amount - (allocated or 0)
        if outstanding <= 0:
            continue
        days_overdue = (as_of - invoice.due_date).days
        for rule in rules:
            key = (invoice.invoice_id, rule.rule_id)
            if days_overdue >= rule.days_overdue and key not in existing_pairs:
                action = CollectionActionDB(
                    invoice_id=invoice.invoice_id,
                    rule_id=rule.rule_id,
                    action_type=rule.action_type,
                    status=CollectionActionStatus.scheduled,
                    scheduled_date=as_of,
                )
                db.add(action)
                created.append(action)
                existing_pairs.add(key)

    try:
        db.commit()
    except IntegrityError:
        # A concurrent run may have scheduled the same invoice/rule pair.
        db.rollback()
        return []
    for action in created:
        db.refresh(action)
    return created


@router.get("/actions", response_model=list[CollectionActionResponse])
def list_collection_actions(
    status: CollectionActionStatus | None = None,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(CollectionActionDB)
    if status is not None:
        query = query.filter(CollectionActionDB.status == status)
    return query.order_by(CollectionActionDB.scheduled_date, CollectionActionDB.action_id).offset(offset).limit(limit).all()


@router.put("/actions/{action_id}", response_model=CollectionActionResponse)
def record_collection_outcome(
    action_id: int, outcome: CollectionActionOutcome, db: Session = Depends(get_db)
):
    action = db.query(CollectionActionDB).filter(CollectionActionDB.action_id == action_id).first()
    if not action:
        raise HTTPException(status_code=404, detail="Collection action not found")
    if outcome.status == CollectionActionStatus.scheduled:
        raise HTTPException(status_code=400, detail="Outcome must be COMPLETED or FAILED")
    if action.status != CollectionActionStatus.scheduled:
        if action.status == outcome.status and action.outcome == outcome.outcome:
            return action
        raise HTTPException(status_code=409, detail="Collection action already has a recorded outcome")
    action.status = outcome.status
    action.outcome = outcome.outcome
    action.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(action)
    return action
