from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def capital_root():
    return {"msg": "资金流向数据需要东方财富接口，当前环境不可用。可手动集成 AkShare 部署在有外网访问的环境。"}


@router.get("/northbound")
async def northbound():
    return []


@router.get("/northbound-holdings")
async def northbound_holdings():
    return []


@router.get("/main-flow")
async def main_flow():
    return []


@router.get("/dragon-tiger")
async def dragon_tiger():
    return []
