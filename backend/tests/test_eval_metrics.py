from scripts.eval_grading import LEVELS, PRED_GRID, confusion, metrics, qwk


def test_qwk_concordancia_perfeita_e_inversa():
    gold = [0, 40, 80, 120, 160, 200]
    assert qwk(gold, gold, LEVELS) == 1.0
    assert qwk(gold, list(reversed(gold)), LEVELS) < 0


def test_metricas_basicas():
    gold = [120, 120, 160, 80]
    pred = [120, 160, 140, 200]
    m = metrics(gold, pred, PRED_GRID, 40)
    assert m["exact"] == 25.0
    assert m["within"] == 75.0
    assert m["mae"] == 45.0
    assert m["bias"] == 35.0  # (0 + 40 - 20 + 120) / 4


def test_confusao_arredonda_para_o_nivel():
    m = confusion([120, 160], [140, 160])
    assert m[LEVELS.index(120)][LEVELS.index(120)] == 1  # 140 vira 120 (empate: menor)
    assert m[LEVELS.index(160)][LEVELS.index(160)] == 1
