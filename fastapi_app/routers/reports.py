from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Optional
from fastapi_app.core.security import get_current_user
from fastapi_app.database.connection import get_db
from fastapi_app.database.models import Report
from fastapi_app.schemas import ReportResponse, ReportListData, ReportItem

router = APIRouter(tags=["Water Resource Reports & Analytics"], dependencies=[Depends(get_current_user)])


class ReportQueryRequest(BaseModel):
    category: Optional[str] = Field(None, description="Filter by category (GROUNDWATER, LEAKAGE, SHORTAGE)")

@router.get(
    "/reports",
    response_model=ReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Water Resource Intelligence Reports (GET)"
)
async def get_reports(
    category: Optional[str] = Query(None, description="Filter by category (GROUNDWATER, LEAKAGE, SHORTAGE)"),
    search: Optional[str] = Query(None, description="Search term in title or summary"),
    db: Session = Depends(get_db)
):
    query = db.query(Report)
    
    if category:
        query = query.filter(Report.category == category.upper())
        
    if search:
        s = f"%{search}%"
        query = query.filter((Report.title.like(s)) | (Report.summary.like(s)))
        
    reports_list = query.all()
    
    formatted_reports = [
        ReportItem(
            report_id=r.id,
            title=r.title,
            date_generated=r.date_generated.isoformat() if hasattr(r.date_generated, 'isoformat') else str(r.date_generated),
            author=r.author,
            category=r.category,
            summary=r.summary,
            key_metrics=r.key_metrics or {},
            status=r.status
        )
        for r in reports_list
    ]

    return ReportResponse(
        data=ReportListData(
            total_reports=len(formatted_reports),
            filter_applied=category or search or "ALL",
            reports=formatted_reports
        )
    )

@router.post(
    "/reports",
    response_model=ReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Query or Generate Intelligence Reports (POST)"
)
async def post_reports(payload: ReportQueryRequest, db: Session = Depends(get_db)):
    category = payload.category
    query = db.query(Report)
    
    if category:
        query = query.filter(Report.category == category.upper())
        
    reports_list = query.all()
    
    formatted_reports = [
        ReportItem(
            report_id=r.id,
            title=r.title,
            date_generated=r.date_generated.isoformat() if hasattr(r.date_generated, 'isoformat') else str(r.date_generated),
            author=r.author,
            category=r.category,
            summary=r.summary,
            key_metrics=r.key_metrics or {},
            status=r.status
        )
        for r in reports_list
    ]

    return ReportResponse(
        data=ReportListData(
            total_reports=len(formatted_reports),
            filter_applied=category or "CUSTOM_QUERY",
            reports=formatted_reports
        )
    )
