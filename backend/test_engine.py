import sys
sys.path.insert(0, '/home/z/my-project/stock-scoring/backend')
from app.scoring.engine import ScoreEngine
from app.routers.scoring import _calc_technical

e = ScoreEngine()

# UP trend
tech = []
for i in range(100):
    tech.append({'close': float(10+i*0.12), 'open': float(10+i*0.12-0.05), 'high': float(10+i*0.12+0.2), 'low': float(10+i*0.12-0.1), 'volume': float(1000000+i*20000), 'date': 'd'+str(i)})
t = _calc_technical(tech)
info = {'pe': 15, 'pb': 1.2, 'market_cap': 500000, 'float_cap': 400000, 'turnover_rate': 3.0, 'amplitude': 3.5, 'change_pct': 2.0, 'amount': 50000000}
r1 = e.score_stock('000001', 'UP', t, info, {})
print('UP: score=' + str(r1.total_score) + ' signal=' + r1.signal)

# DOWN trend
tech2 = []
p = 20.0
for i in range(100):
    p -= 0.1
    tech2.append({'close': float(p), 'open': float(p+0.05), 'high': float(p+0.1), 'low': float(p-0.15), 'volume': float(2000000-i*15000), 'date': 'd'+str(i)})
t2 = _calc_technical(tech2)
info2 = {'pe': 90, 'pb': 7, 'market_cap': 5000000, 'float_cap': 4000000, 'turnover_rate': 12, 'amplitude': 8, 'change_pct': -4.0, 'amount': 20000000}
r2 = e.score_stock('600000', 'DN', t2, info2, {})
print('DN: score=' + str(r2.total_score) + ' signal=' + r2.signal)

assert r1.total_score > r2.total_score, f"UP({r1.total_score}) should > DN({r2.total_score})"
print('ASSERTION PASSED')
