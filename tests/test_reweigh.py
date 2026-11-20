from app.engine import evaluate
from app.config import ROOT
from app.modules.reweigh.rules import inherit_reweigh
from app.modules.pairing.rules import pair

def rw():
    return evaluate({'dataset':'reweigh'})

def test_reweigh_adopted_count_real():
    s=rw()
    # 01001、01002、01003v2、01003v3 四张补秤票进入可付款结果
    assert s['counts']['reweigh_adopted']==4
    assert len(s['reweighs'])==4

def test_inherited_tare_and_deal_real():
    s=rw();first=s['reweighs'][0]
    assert first['ticket']=='01001'
    # 补秤单只带新毛重：皮重、单价、扣杂率全部沿用同票原票，不跨票拼接
    assert first['tare_kg']=='10'
    assert first['price']=='12.30'
    assert first['rate']=='0.05'
    assert first['tare_source']=='沿用票01001版本1皮重(行3)'
    assert first['base_lines']==[2,3]
    assert first['reweigh_line']==16

def test_before_after_diff_real():
    s=rw();first=next(r for r in s['reweighs'] if r['ticket']=='01001')
    # (110-10)*0.95*12.30=1168.50；原票 (100-10)*0.95*12.30=1051.65
    assert first['gross_delta_kg']=='10'
    assert first['amount_before']=='1051.65'
    assert first['amount']=='1168.50'
    assert first['amount_delta']=='116.85'

def test_explicit_deal_fields_matching_base_real():
    s=rw();row=next(r for r in s['reweighs'] if r['ticket']=='01002')
    # 补秤单显式填写且与原票一致的成交依据同样采纳
    assert row['amount_before']=='929.28'
    assert row['amount']=='992.64'
    assert row['amount_delta']=='63.36'

def test_chained_reweigh_real():
    s=rw();chain=[r for r in s['reweighs'] if r['ticket']=='01003']
    assert [r['version'] for r in chain]==[2,3]
    v2,v3=chain
    assert v2['amount']=='2196.78' and v3['amount_before']=='2196.78'
    assert v3['amount']=='2243.52' and v3['amount_delta']=='46.74'
    # 链上每一版都沿用同一张原皮重证据
    assert v3['tare_kg']=='20' and v3['base_version']==2

def test_missing_original_blocked_real():
    s=rw();q=next(q for q in s['quarantine'] if q['id']=='rw-missing')
    assert q['code']=='REWEIGH_NO_ORIGINAL'

def test_fish_mismatch_blocked_real():
    s=rw();q=next(q for q in s['quarantine'] if q['id']=='rw-fish')
    assert q['code']=='REWEIGH_FISH_MISMATCH'

def test_deal_mismatch_blocked_real():
    s=rw();q=next(q for q in s['quarantine'] if q['id']=='rw-deal')
    assert q['code']=='REWEIGH_DEAL_MISMATCH'

def test_negative_net_blocked_real():
    s=rw();q=next(q for q in s['quarantine'] if q['id']=='rw-negative')
    assert q['code']=='REWEIGH_NEGATIVE_NET'

def test_blocked_keeps_original_result_real():
    s=rw()
    # 阻断票不进入可付款结果，旧版 v1 结果与原始称重证据保留
    finals={f['ticket']:f for f in s['final']}
    for ticket in ('01004','01005','01006','01007'):
        assert finals[ticket]['version']==1
        assert finals[ticket]['amount']=='1051.65'
    assert not any(r['ticket'] in {'01004','01005','01006','01007'} for r in s['reweighs'])

def test_conflicting_duplicate_all_quarantined_real():
    s=rw()
    dup=[q for q in s['quarantine'] if q['code']=='REWEIGH_DUPLICATE']
    assert {q['id'] for q in dup}=={'rw007a','rw007b','rw007c'}
    assert s['counts']['reweigh_duplicate']==0
    # 原始称重证据完整保留
    assert {q['raw']['weight'] for q in dup}=={'105','105','109'}

def test_identical_duplicate_adopted_once():
    text=(ROOT/'sample_data/reweigh.csv').read_text()
    # 同票同版本同值补秤再到达一次：重跑不新增票、不重复补款
    duplicated=text+"\nrw001-again,01001,gross,110,kg,黄鱼,,,2,1,\n"
    s=evaluate({'csv_text':duplicated})
    adopted=[r for r in s['reweighs'] if r['ticket']=='01001']
    assert len(adopted)==1
    assert adopted[0]['amount']=='1168.50'
    assert s['counts']['reweigh_duplicate']==1

def test_rerun_idempotent_real():
    a=evaluate({'dataset':'reweigh'});b=evaluate({'dataset':'reweigh'})
    assert a['manifest']['run_id']==b['manifest']['run_id']
    assert a['reweighs']==b['reweighs']
    assert len(a['reweighs'])==len(b['reweighs'])==4

def test_row_conservation_real():
    s=rw();b=s['balance']
    # 输入行 = 常规采纳 + 隔离 + 空行/表头/重复 + 补秤采纳 + 同值补秤重复
    assert b['row_balanced'] is True
    assert b['input']==25

def test_reweigh_blocked_counts_real():
    s=rw()
    assert s['balance']['blocked']==7
    assert s['archive']['status']=='待处理'

def test_unit_inherit_reweigh_direct(clean):
    # 单元级：留空成交字段继承原票；冲突行进入隔离且不产生结果
    pairs,bad,reweighs=pair(clean['records'])
    assert bad==[] and reweighs==[]
    state={'quarantine':[]}
    row=dict(clean['records'][0],version=2,replaces='1',price='',rate='',paid='',id='rw-x',_line=99)
    results,blocked,duplicate=inherit_reweigh(state,[row],pairs)
    assert duplicate==0 and blocked==[]
    assert results[0]['tare_kg']=='15'
    assert results[0]['price']=='12.30' and results[0]['rate']=='0.05'

def test_unit_missing_base_blocks():
    state={'quarantine':[]}
    row={'ticket':'X','version':2,'replaces':'1','fish':'黄鱼','weight_kg':'50',
         'price':'','rate':'','paid':'','_line':9,'id':'rw'}
    results,blocked,_=inherit_reweigh(state,[row],[])
    assert results==[] and len(blocked)==1
    assert state['quarantine'][0]['code']=='REWEIGH_NO_ORIGINAL'

def test_dirty_and_legacy_unchanged_real(sample,clean):
    # 旧样例无补秤单，新增模块不改变既有可付款结果
    assert sample['counts']['reweigh_adopted']==0
    assert sample['balance']['due']=='22540.41'
    assert clean['archive']['tickets']==20
    assert sample['manifest']['run_id']!=clean['manifest']['run_id']
