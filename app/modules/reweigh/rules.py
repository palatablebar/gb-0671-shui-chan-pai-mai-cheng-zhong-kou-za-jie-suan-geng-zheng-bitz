from collections import defaultdict
from decimal import Decimal
from app.reasons import reject
from app.modules.auction.rules import settle

def inherit_reweigh(state, reweighs, pairs):
    # 已生效毛皮配对按 票号+版本 建索引，补秤合成后立即补入，支持链式补秤
    index={(p['ticket'],p['version']):p for p in pairs}
    grouped=defaultdict(list)
    for row in reweighs: grouped[(row['ticket'],row['version'])].append(row)
    results=[];blocked=[];duplicate=0
    for (ticket,version),items in sorted(grouped.items()):
        weights={r['weight_kg'] for r in items}
        if len(weights)>1:
            # 同一补秤重复到达但新毛重冲突：全部隔离，旧版结果与原始证据保留
            for row in items:
                reject(state,row,'REWEIGH_DUPLICATE','同票同版本补秤新毛重不一致，全部隔离')
                blocked.append(row)
            continue
        row=items[0]
        if len(items)>1: duplicate+=len(items)-1
        target=row['replaces'].strip()
        base=index.get((ticket,int(target)))
        # 边界一：必须能找到同票同版本的原票
        if base is None:
            reject(state,row,'REWEIGH_NO_ORIGINAL',f'票{ticket}缺少版本{target}的原票')
            blocked.append(row);continue
        # 边界二：沿用皮重的品类必须与补秤单一致，禁止跨品类拼接证据
        if row['fish']!=base['fish']:
            reject(state,row,'REWEIGH_FISH_MISMATCH',f"补秤品类{row['fish']}与原票{base['fish']}不一致")
            blocked.append(row);continue
        # 边界三：成交依据必须一致；留空字段继承原票，禁止跨票拼接
        price=row['price'] or base['price'];rate=row['rate'] or base['rate']
        if row['price'] and row['price']!=base['price'] or row['rate'] and row['rate']!=base['rate']:
            reject(state,row,'REWEIGH_DEAL_MISMATCH','单价或扣杂率与原票成交依据不一致')
            blocked.append(row);continue
        net=Decimal(row['weight_kg'])-Decimal(base['tare_kg'])
        # 边界四：沿用原皮重后净重不得为负
        if net<0:
            reject(state,row,'REWEIGH_NEGATIVE_NET',f"新毛重{row['weight_kg']}kg小于沿用皮重{base['tare_kg']}kg")
            blocked.append(row);continue
        before=settle(base)
        synthesized={'ticket':ticket,'version':version,'fish':row['fish'],
            'gross_kg':row['weight_kg'],'tare_kg':base['tare_kg'],'net_kg':str(net),
            'price':price,'rate':rate,'replaces':row['replaces'],
            'paid':row['paid'] or base['paid'],'lines':[row['_line']]+base['lines']}
        current=settle(synthesized)
        result={**current,
            'base_version':int(target),'base_gross_kg':base['gross_kg'],
            'gross_delta_kg':str(Decimal(row['weight_kg'])-Decimal(base['gross_kg'])),
            'amount_before':before['amount'],
            'amount_delta':str(Decimal(current['amount'])-Decimal(before['amount'])),
            'tare_source':f"沿用票{ticket}版本{target}皮重(行{base['lines'][1]})",
            'base_lines':base['lines'],'reweigh_line':row['_line']}
        results.append(result);index[(ticket,version)]=current
    return results,blocked,duplicate

def apply(state):
    results,blocked,duplicate=inherit_reweigh(state,state['reweigh_candidates'],state['pairs'])
    consumed={r['_line'] for r in state['reweigh_candidates']}
    state['records']=[r for r in state['records'] if r['_line'] not in consumed]
    state['pairs'].extend(results)
    state['reweighs']=results
    state['counts']['reweigh_adopted']=len(results)
    state['counts']['reweigh_duplicate']=duplicate
    state['views']['reweigh']={'title':'补秤结算','rows':results,
        'metrics':{'补秤采纳':len(results),'补秤阻断':len(blocked),'补秤重复':duplicate}}
