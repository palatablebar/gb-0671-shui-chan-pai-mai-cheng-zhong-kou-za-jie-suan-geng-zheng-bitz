import unicodedata
from app.coerce import number
from app.config import SENTINELS
from app.errors import BusinessError
from app.reasons import reject

def blank(value):
    return unicodedata.normalize('NFKC', str(value)).strip() in SENTINELS

def normalize(row):
    out=dict(row)
    factor={'kg':1,'t':1000,'公斤':1}.get(row['unit'])
    if factor is None: raise BusinessError('BAD_UNIT','称重单位不受支持')
    if row['kind'] not in {'gross','tare'}: raise BusinessError('BAD_KIND','称重类型无效')
    weight=number(row['weight'])*factor
    version=number(row['version'])
    if weight<0 or version<1 or version%1:
        raise BusinessError('INVALID_RANGE','重量或版本越界')
    # 补秤单只带新毛重：单价/扣杂率/已付允许留空，空值表示沿用上一版原票证据
    inherit=row['kind']=='gross' and version>=2 and row['replaces'].strip()
    price='' if inherit and blank(row['price']) else number(row['price'])
    rate='' if inherit and blank(row['rate']) else number(row['rate'])
    paid='' if inherit and blank(row['paid']) else number(row['paid'])
    if (price!='' and price<0) or (rate!='' and not 0<=rate<1) or (paid!='' and paid<0):
        raise BusinessError('INVALID_RANGE','单价、扣杂率或已付越界')
    out.update(weight_kg=str(weight),
        price='' if price=='' else str(price),
        rate='' if rate=='' else str(rate),
        paid='' if paid=='' else str(paid),
        version=int(version))
    if not row['ticket'].strip() or not row['fish'].strip(): raise BusinessError('UNKNOWN_REFERENCE','票号或品类缺失')
    return out

def apply(state):
    good=[]
    for row in state['records']:
        try: good.append(normalize(row))
        except BusinessError as error: reject(state,row,error.code,error.message)
    state['records']=good
    state['views']['conversion']={'title':'重量换算','rows':good,'metrics':{'规范行':len(good),'隔离行':len(state['quarantine'])}}
