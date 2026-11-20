from fastapi import APIRouter, Request, Body
from app.engine import evaluate
from app.web import render
router=APIRouter()
@router.get('/reweigh')
def page(request:Request):
    return render(request,'reweigh')
@router.post('/api/reweigh')
def calculate(payload:dict=Body(default={})):
    return evaluate(payload,until=4)
