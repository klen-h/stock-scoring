from fastapi import APIRouter

router = APIRouter()


@router.get("/industry")
async def sector_industry():
    return []


@router.get("/concept")
async def sector_concept():
    return []


@router.get("/industry-flow")
async def sector_industry_flow():
    return []


@router.get("/concept-flow")
async def sector_concept_flow():
    return []
